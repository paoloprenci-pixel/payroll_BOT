import subprocess
import os

PROJECT_ID = "gen-lang-client-0296046668"
SA_NAME = "github-deploy-sa"
SA_EMAIL = f"{SA_NAME}@{PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE = "service-account-key.json"

ROLES = [
    "roles/cloudfunctions.admin",
    "roles/cloudbuild.builds.editor",
    "roles/secretmanager.secretAccessor",
    "roles/iam.serviceAccountUser",
    "roles/storage.admin"
]

def run_cmd(cmd):
    # Quote arguments with spaces for shell=True on Windows
    quoted_cmd = []
    for arg in cmd:
        if " " in arg:
            quoted_cmd.append(f'"{arg}"')
        else:
            quoted_cmd.append(arg)
    
    full_cmd = " ".join(quoted_cmd)
    print(f"Running: {full_cmd}")
    result = subprocess.run(full_cmd, capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        print(f"Warning/Error: {result.stderr}")
    return result

def setup_sa():
    # 1. Create SA
    run_cmd(["gcloud", "iam", "service-accounts", "create", SA_NAME, "--display-name", "GitHub Deploy Service Account", "--project", PROJECT_ID, "--quiet"])

    # 2. Add Roles
    for role in ROLES:
        run_cmd(["gcloud", "projects", "add-iam-policy-binding", PROJECT_ID, "--member", f"serviceAccount:{SA_EMAIL}", "--role", role, "--quiet"])

    # 3. Create Key
    if os.path.exists(KEY_FILE):
        os.remove(KEY_FILE)
    
    result = run_cmd(["gcloud", "iam", "service-accounts", "keys", "create", KEY_FILE, "--iam-account", SA_EMAIL, "--project", PROJECT_ID])
    
    if os.path.exists(KEY_FILE) and os.path.getsize(KEY_FILE) > 0:
        print("\n✅ Key generated successfully!")
        with open(KEY_FILE, "r") as f:
            print("\n--- BEGIN SERVICE ACCOUNT KEY ---")
            print(f.read())
            print("--- END SERVICE ACCOUNT KEY ---")
    else:
        print("\n❌ Failed to generate key.")

if __name__ == "__main__":
    setup_sa()
