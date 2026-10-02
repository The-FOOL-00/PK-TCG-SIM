import os, sys, subprocess, json
from collections import defaultdict

root = os.path.abspath('.')

# Load before numbers
with open('research/repository_cleanup/size_raw.json', 'r') as f:
    before = json.load(f)

# Tracked files
p = subprocess.run(['git', 'ls-files', '-z'], capture_output=True)
tracked_rel = set(os.path.normpath(f) for f in p.stdout.decode('utf-8', errors='replace').split('\0') if f)

# Untracked files
p = subprocess.run(['git', 'ls-files', '--others', '--exclude-standard', '-z'], capture_output=True)
untracked_rel = set(os.path.normpath(f) for f in p.stdout.decode('utf-8', errors='replace').split('\0') if f)

total_size = 0
git_size = 0
working_tree_size = 0
tracked_size = 0
untracked_size = 0
ignored_size = 0
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
        total_size += sz
        rel = os.path.normpath(os.path.relpath(fp, root))
        if rel.startswith('.git') or rel == '.git':
            git_size += sz
            cat = 'git'
        else:
            working_tree_size += sz
            if rel in tracked_rel:
                tracked_size += sz
                cat = 'tracked'
            elif rel in untracked_rel:
                untracked_size += sz
                cat = 'untracked'
            else:
                ignored_size += sz
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

def fmt(b):
    for u in ['B', 'KB', 'MB', 'GB', 'TB']:
        if b < 1024.0: return f'{b:.2f} {u}'
        b /= 1024.0
    return f'{b:.2f} PB'

reclaimed = before['total_workspace_size'] - total_size
pct_reclaimed = (reclaimed / before['total_workspace_size']) * 100

print('=== POST-CLEANUP SIZE AUDIT ===')
print(f'BEFORE Total Workspace:   {fmt(before["total_workspace_size"])}')
print(f'AFTER Total Workspace:    {fmt(total_size)}')
print(f'SPACE RECLAIMED:          {fmt(reclaimed)} ({pct_reclaimed:.2f}%)')
print(f'Working Tree (excl .git): {fmt(working_tree_size)}')
print(f'.git Internal Size:       {fmt(git_size)}')
print(f'Tracked Files Size:       {fmt(tracked_size)}')
print(f'Untracked Files Size:     {fmt(untracked_size)}')
print(f'Ignored Files Size:       {fmt(ignored_size)}')
print(f'Total File Count:         {len(all_files)} (Before: {before["total_files"]}, Reclaimed: {before["total_files"] - len(all_files)} files)')

all_files.sort(key=lambda x: x[0], reverse=True)
print('\nTop 10 Remaining Files:')
for sz, rel, cat in all_files[:10]:
    print(f'  {fmt(sz)}: {rel} ({cat})')

sorted_dirs = sorted(
    [(d, sz, dir_recursive_counts[d]) for d, sz in dir_recursive_sizes.items() if d != '.' and not d.startswith('.git')],
    key=lambda x: x[1],
    reverse=True
)
print('\nTop 10 Remaining Directories:')
for d, sz, cnt in sorted_dirs[:10]:
    print(f'  {fmt(sz)}: {d} ({cnt} files)')

# Save post cleanup data for report
with open('research/repository_cleanup/size_post.json', 'w') as f:
    json.dump({
        'before_workspace': before['total_workspace_size'],
        'after_workspace': total_size,
        'space_reclaimed': reclaimed,
        'working_tree': working_tree_size,
        'git_size': git_size,
        'tracked_size': tracked_size,
        'untracked_size': untracked_size,
        'ignored_size': ignored_size,
        'before_files': before['total_files'],
        'after_files': len(all_files)
    }, f, indent=2)
