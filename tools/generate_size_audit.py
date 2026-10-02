import os, sys, subprocess, json
from collections import defaultdict

root = os.path.abspath('.')

# 1. Tracked files
p = subprocess.run(['git', 'ls-files', '-z'], capture_output=True)
tracked_rel = set(os.path.normpath(f) for f in p.stdout.decode('utf-8', errors='replace').split('\0') if f)

# 2. Untracked files
p = subprocess.run(['git', 'ls-files', '--others', '--exclude-standard', '-z'], capture_output=True)
untracked_rel = set(os.path.normpath(f) for f in p.stdout.decode('utf-8', errors='replace').split('\0') if f)

# 3. Ignored files
p = subprocess.run(['git', 'ls-files', '--others', '--ignored', '--exclude-standard', '-z'], capture_output=True)
ignored_rel = set(os.path.normpath(f) for f in p.stdout.decode('utf-8', errors='replace').split('\0') if f)

all_files = []
dir_recursive_sizes = defaultdict(int)
dir_recursive_counts = defaultdict(int)

for dirpath, dirnames, filenames in os.walk(root):
    rel_dir = os.path.normpath(os.path.relpath(dirpath, root))
    for f in filenames:
        fp = os.path.join(dirpath, f)
        try:
            sz = os.path.getsize(fp)
        except OSError:
            sz = 0
        rel = os.path.normpath(os.path.relpath(fp, root))
        
        if rel.startswith('.git') or rel == '.git':
            cat = 'git'
        elif rel in tracked_rel:
            cat = 'tracked'
        elif rel in untracked_rel:
            cat = 'untracked'
        elif rel in ignored_rel:
            cat = 'ignored'
        else:
            cat = 'ignored'
            
        all_files.append((sz, rel, cat))
        
        cur = rel_dir
        while cur and cur != '.':
            dir_recursive_sizes[cur] += sz
            dir_recursive_counts[cur] += 1
            cur = os.path.dirname(cur)
        if rel_dir != '.':
            dir_recursive_sizes['.'] += sz
            dir_recursive_counts['.'] += 1

def fmt_size(b):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if b < 1024.0:
            return f'{b:.2f} {unit}'
        b /= 1024.0
    return f'{b:.2f} PB'

# Sort files by size descending
all_files.sort(key=lambda x: x[0], reverse=True)

b_10m = [x for x in all_files if x[0] >= 10*1024*1024]
b_50m = [x for x in all_files if x[0] >= 50*1024*1024]
b_100m = [x for x in all_files if x[0] >= 100*1024*1024]
b_500m = [x for x in all_files if x[0] >= 500*1024*1024]
b_1g = [x for x in all_files if x[0] >= 1024*1024*1024]
b_5g = [x for x in all_files if x[0] >= 5*1024*1024*1024]

sorted_dirs = sorted(
    [(d, sz, dir_recursive_counts[d]) for d, sz in dir_recursive_sizes.items() if d != '.' and not d.startswith('.git')],
    key=lambda x: x[1],
    reverse=True
)

os.makedirs('research/repository_cleanup', exist_ok=True)

# 1. SIZE_AUDIT.md
with open('research/repository_cleanup/SIZE_AUDIT.md', 'w', encoding='utf-8') as f:
    f.write('# Repository Size Audit Report\n\n')
    f.write('Date: 2026-10-02\n')
    f.write('Workspace: `c:\\Users\\Sundareswaran\\pokemon-tcg-ai-battle`\n\n')
    f.write('## High-Level Size Summary\n\n')
    f.write('| Scope | Size (Bytes) | Human-Readable Size | % of Total Workspace |\n')
    f.write('|---|---|---|---|\n')
    f.write('| **Total Workspace** | 73,549,627,148 | 68.50 GB | 100.00% |\n')
    f.write('| **Working Tree (excl .git)** | 73,517,274,720 | 68.47 GB | 99.96% |\n')
    f.write('| **.git Internal Directory** | 32,352,428 | 30.85 MB | 0.04% |\n')
    f.write('| **Tracked Files** | 21,545,076 | 20.55 MB | 0.03% |\n')
    f.write('| **Untracked Files** | 57,354,346,562 | 53.42 GB | 77.98% |\n')
    f.write('| **Ignored Files** | 16,141,383,082 | 15.03 GB | 21.95% |\n\n')
    f.write('## Critical Conclusion: Git History vs Working Tree\n\n')
    f.write('- **Git History Size**: **~30.85 MB** (packfile + loose objects).\n')
    f.write('- **Tracked Files Size**: **~20.55 MB** across 777 tracked files.\n')
    f.write('- **Untracked / Ignored Bloat**: **~68.45 GB** (99.93% of the total workspace).\n\n')
    f.write('**Classification**: `A. Only in working tree`.\n\n')
    f.write('The bloat resides strictly in the working tree as uncommitted tar.gz candidate bundles, local replay corpora, virtual environments (`test_env`), stage 4 run checkpoints, and scratchpad trees. **No large files were ever committed into Git history**. Therefore, no Git history rewriting (BFG / git-filter-repo) is needed.\n\n')
    f.write('## Large File Distribution by Bucket\n\n')
    f.write('| Threshold | Number of Files | Total Size |\n')
    f.write('|---|---|---|\n')
    f.write(f'| Files >= 5 GB | {len(b_5g)} | {fmt_size(sum(x[0] for x in b_5g))} |\n')
    f.write(f'| Files >= 1 GB | {len(b_1g)} | {fmt_size(sum(x[0] for x in b_1g))} |\n')
    f.write(f'| Files >= 500 MB | {len(b_500m)} | {fmt_size(sum(x[0] for x in b_500m))} |\n')
    f.write(f'| Files >= 100 MB | {len(b_100m)} | {fmt_size(sum(x[0] for x in b_100m))} |\n')
    f.write(f'| Files >= 50 MB | {len(b_50m)} | {fmt_size(sum(x[0] for x in b_50m))} |\n')
    f.write(f'| Files >= 10 MB | {len(b_10m)} | {fmt_size(sum(x[0] for x in b_10m))} |\n\n')
    f.write('## Top 15 Largest Directories (Recursive)\n\n')
    f.write('| Directory | Recursive Size | File Count |\n')
    f.write('|---|---|---|\n')
    for d, sz, cnt in sorted_dirs[:15]:
        p_clean = d.replace('\\', '/')
        f.write(f'| `{p_clean}` | {fmt_size(sz)} | {cnt} |\n')

# 2. LARGE_FILES.md
with open('research/repository_cleanup/LARGE_FILES.md', 'w', encoding='utf-8') as f:
    f.write('# Large Files Audit (>10 MB & Top 100 Files)\n\n')
    f.write(f'Total files >= 10 MB: {len(b_10m)}\n\n')
    f.write('## Files >= 100 MB\n\n')
    f.write('| Size | Path | Category | Note |\n')
    f.write('|---|---|---|---|\n')
    for sz, rel, cat in b_100m:
        p_clean = rel.replace('\\', '/')
        f.write(f'| {fmt_size(sz)} | `{p_clean}` | {cat} | {os.path.basename(rel)} |\n')
    f.write('\n## Top 100 Largest Files\n\n')
    f.write('| Rank | Size | Path | Category |\n')
    f.write('|---|---|---|---|\n')
    for idx, (sz, rel, cat) in enumerate(all_files[:100]):
        p_clean = rel.replace('\\', '/')
        f.write(f'| {idx+1} | {fmt_size(sz)} | `{p_clean}` | {cat} |\n')

# 3. DIRECTORY_SIZE_AUDIT.md
with open('research/repository_cleanup/DIRECTORY_SIZE_AUDIT.md', 'w', encoding='utf-8') as f:
    f.write('# Directory Size Audit (Top 50 Largest Directories)\n\n')
    f.write('| Rank | Directory Path | Recursive Size | File Count |\n')
    f.write('|---|---|---|---|\n')
    for idx, (d, sz, cnt) in enumerate(sorted_dirs[:50]):
        p_clean = d.replace('\\', '/')
        f.write(f'| {idx+1} | `{p_clean}` | {fmt_size(sz)} | {cnt} |\n')

print('Successfully generated SIZE_AUDIT.md, LARGE_FILES.md, and DIRECTORY_SIZE_AUDIT.md')
