import os
import subprocess

def setup_git_hooks():
    """Configure Git hooks after package installation."""
    try:
        repo_root = os.path.dirname(
            os.path.abspath(__file__)
        )
        hooks_path = os.path.join(repo_root, ".githooks")
        
        if os.path.exists(hooks_path):
            subprocess.run(
                ["git", "config", "core.hooksPath",
                 ".githooks"],
                cwd=repo_root,
                check=True
            )
            print("Git hooks configured successfully")
        else:
            print("Warning: .githooks directory not found")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Could not configure hooks: {e}")
    except Exception as e:
        print(f"Warning: Setup error: {e}")

if __name__ == "__main__":
    setup_git_hooks()
