import os, sys, json, hashlib, shutil

def run_phase_1():
    print("====================================================================")
    print("=== PHASE 1: FREEZE CANDIDATE SNAPSHOT & MANIFEST GENERATION ===")
    print("====================================================================")

    frozen_dir = 'project_mew_aggressive_surgical_frozen'
    os.makedirs(frozen_dir, exist_ok=True)
    os.makedirs(os.path.join(frozen_dir, 'bot'), exist_ok=True)
    os.makedirs(os.path.join(frozen_dir, 'final_build'), exist_ok=True)

    # 1. Copy policy and support
    src_policy = 'project_mew_aggressive_surgical/policies/aggressive_surgical_policy.py'
    dst_policy = os.path.join(frozen_dir, 'bot', 'aggressive_surgical_policy.py')
    shutil.copy(src_policy, dst_policy)

    src_init = os.path.join('project_mew_aggressive_surgical/build_candidate/bot/__init__.py')
    if os.path.exists(src_init):
        shutil.copy(src_init, os.path.join(frozen_dir, 'bot', '__init__.py'))
    else:
        with open(os.path.join(frozen_dir, 'bot', '__init__.py'), 'w') as f:
            f.write('"""Bot package."""\n')

    # 2. Copy deck
    src_deck = 'project_mew_aggressive_surgical/decks/deck_alakazam_master.csv'
    dst_deck = os.path.join(frozen_dir, 'deck.csv')
    shutil.copy(src_deck, dst_deck)

    # 3. Copy main.py
    src_main = 'project_mew_aggressive_surgical/build_candidate/main.py'
    dst_main = os.path.join(frozen_dir, 'main.py')
    shutil.copy(src_main, dst_main)

    # 4. Copy reference candidate tarball
    cand_tar = 'project_mew_aggressive_surgical/artifacts/project_mew_aggressive_surgical_candidate.tar.gz'
    shutil.copy(cand_tar, os.path.join(frozen_dir, 'project_mew_aggressive_surgical_candidate.tar.gz'))

    def sha256_file(path):
        with open(path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    manifest = []
    for root, dirs, files in os.walk(frozen_dir):
        for fl in files:
            full_p = os.path.join(root, fl)
            rel_p = os.path.relpath(full_p, frozen_dir)
            size = os.path.getsize(full_p)
            h = sha256_file(full_p)
            manifest.append({
                'rel_path': rel_p,
                'size_bytes': size,
                'sha256': h,
                'runtime_required': fl in ['main.py', 'deck.csv', 'aggressive_surgical_policy.py', '__init__.py'],
                'runtime_reachable': True
            })

    manifest_path = os.path.join(frozen_dir, 'final_build', 'artifact_manifest_prebuild.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print('Frozen Snapshot Created at:', frozen_dir)
    for item in manifest:
        print(f"  {item['rel_path']:50s} | Size: {item['size_bytes']:6d} B | SHA256: {item['sha256']}")

if __name__ == '__main__':
    run_phase_1()
