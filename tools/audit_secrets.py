import os, subprocess, re

patterns = [
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----',
    r'kaggle\.json',
    r'credentials\.json',
    r'\.env$',
    r'id_rsa',
    r'id_ed25519',
    r'api[_-]?key\s*[:=]\s*[\'"][A-Za-z0-9_\-]{16,}[\'"]',
    r'bearer\s+[A-Za-z0-9_\-\.]{20,}',
    r'secret\s*[:=]\s*[\'"][A-Za-z0-9_\-]{16,}[\'"]',
    r'password\s*[:=]\s*[\'"][A-Za-z0-9_\-]{8,}[\'"]',
    r'ghp_[A-Za-z0-9]{36}',
    r'github_pat_[A-Za-z0-9_]{82}'
]

compiled = [re.compile(p, re.IGNORECASE) for p in patterns]

print('1. Checking file names in workspace for secret patterns...')
secret_files = []
for root, _, files in os.walk('.'):
    if '.git' in root: continue
    for f in files:
        fl = f.lower()
        if fl in ['kaggle.json', 'credentials.json', '.env', 'id_rsa', 'id_ed25519'] or fl.endswith(('.pem', '.key')):
            secret_files.append(os.path.join(root, f))

print(f'Secret files found in working tree: {secret_files}')

print('2. Checking git log for secret commits/filenames...')
p = subprocess.run(['git', 'log', '--all', '--name-only', '--oneline'], capture_output=True, text=True)
git_secret_files = []
for line in p.stdout.split('\n'):
    l = line.strip().lower()
    if any(k in l for k in ['kaggle.json', 'credentials.json', '.env', '.pem', '.key', 'id_rsa']):
        git_secret_files.append(line.strip())
print(f'Git history filenames matching secret patterns: {git_secret_files}')

print('3. Searching tracked files for secret patterns...')
p = subprocess.run(['git', 'grep', '-I', '-i', '-E', 'BEGIN (RSA|OPENSSH|DSA|EC)? ?PRIVATE KEY|ghp_|github_pat_'], capture_output=True, text=True)
print(f'Grep private key/tokens in tracked files: stdout={p.stdout.strip()}, stderr={p.stderr.strip()}')

print('4. Checking tracked files for API keys / passwords...')
suspicious_matches = []
p = subprocess.run(['git', 'ls-files', '-z'], capture_output=True)
tracked = [f for f in p.stdout.decode('utf-8', errors='replace').split('\0') if f]
for tf in tracked:
    # Skip binaries
    if tf.endswith(('.npz', '.png', '.jpg', '.pdf', '.zip', '.tar.gz', '.dll', '.exe', '.pkl')):
        continue
    try:
        with open(tf, 'r', encoding='utf-8', errors='ignore') as f:
            for idx, line in enumerate(f, 1):
                for cp in compiled:
                    if cp.search(line):
                        # Filter out known safe words in comments/code
                        if 'api_key' in line.lower() and 'os.environ' in line:
                            continue
                        suspicious_matches.append((tf, idx, line.strip()[:80]))
    except Exception:
        pass

print(f'Suspicious matches in tracked text files: {len(suspicious_matches)}')
for sm in suspicious_matches[:10]:
    print(f'  {sm[0]}:{sm[1]} -> {sm[2]}')

if not secret_files and not git_secret_files and not suspicious_matches:
    print('SECRETS AUDIT VERDICT: PASS (ZERO SECRETS FOUND)')
else:
    print('SECRETS AUDIT VERDICT: REVIEW REQUIRED')
