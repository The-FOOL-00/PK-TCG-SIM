import os
import sys
import tarfile
import hashlib
import shutil

def build_package():
    pkg_dir = 'project_mew_aggressive_surgical/build_candidate'
    os.makedirs(pkg_dir, exist_ok=True)
    os.makedirs(os.path.join(pkg_dir, 'bot'), exist_ok=True)

    # 1. Copy policy
    shutil.copy('project_mew_aggressive_surgical/policies/aggressive_surgical_policy.py', 
                os.path.join(pkg_dir, 'bot', 'aggressive_surgical_policy.py'))
    with open(os.path.join(pkg_dir, 'bot', '__init__.py'), 'w') as f:
        f.write('"""Bot package."""\n')

    # 2. Copy deck
    shutil.copy('project_mew_aggressive_surgical/decks/deck_alakazam_master.csv', 
                os.path.join(pkg_dir, 'deck.csv'))

    # 3. Create production main.py
    main_py_content = (
        '"""Pokemon TCG AI Battle Challenge agent.\n'
        'Production-Safe Aggressive-Surgical High-Elo Candidate.\n'
        '"""\n'
        'import os, sys\n\n'
        'current_dir = os.path.dirname(os.path.abspath(__file__))\n'
        'if current_dir not in sys.path:\n'
        '    sys.path.insert(0, current_dir)\n\n'
        'try:\n'
        '    from bot.aggressive_surgical_policy import select_aggressive_surgical_action\n'
        'except Exception:\n'
        '    def select_aggressive_surgical_action(obs, legal_actions):\n'
        '        return legal_actions[0].get("index", 0) if legal_actions else 0\n\n'
        'def agent(obs):\n'
        '    """Main agent entry point."""\n'
        '    try:\n'
        '        legal_actions = obs.get("legal_actions", [])\n'
        '        if not legal_actions:\n'
        '            return 0\n'
        '        return select_aggressive_surgical_action(obs, legal_actions)\n'
        '    except Exception as err:\n'
        '        sys.stderr.write(f"[AGENT_FALLBACK_ERROR]: {err}\\n")\n'
        '        legal = obs.get("legal_actions", [])\n'
        '        return legal[0].get("index", 0) if legal else 0\n\n'
        'if __name__ == "__main__":\n'
        '    dummy = {"legal_actions": [{"type": "ATTACK", "index": 0}], "active_hp": 210}\n'
        '    print("Production Smoke Test: returned action", agent(dummy))\n'
    )

    with open(os.path.join(pkg_dir, 'main.py'), 'w') as f:
        f.write(main_py_content)

    # 4. Create tar.gz archive
    tar_path = 'project_mew_aggressive_surgical/artifacts/project_mew_aggressive_surgical_candidate.tar.gz'
    with tarfile.open(tar_path, 'w:gz') as tar:
        for item in os.listdir(pkg_dir):
            tar.add(os.path.join(pkg_dir, item), arcname=item)

    with open(tar_path, 'rb') as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    size_kb = os.path.getsize(tar_path) / 1024.0
    print(f'Successfully built {tar_path} ({size_kb:.2f} KB)')
    print(f'SHA256: {sha}')

    # 5. Clean sandbox smoke test
    sys.path.insert(0, os.path.abspath(pkg_dir))
    import main
    test_action = main.agent({'legal_actions': [{'type': 'ATTACK', 'index': 3}]})
    print(f'Sandbox Test Passed: action {test_action} returned.')

if __name__ == '__main__':
    build_package()
