import os
import shutil

def main():
    print("🚀 Welcome to the Auto Resume Builder Setup Wizard!\n")
    
    # --- 1. Environment Variables Setup ---
    print("--- API Key Configuration ---")
    gemini_key = input("Enter your Google Gemini API Key: ").strip()
    github_token = input("Enter your GitHub Personal Access Token (Optional, press Enter to skip): ").strip()
    
    env_content = f"GEMINI_API_KEY={gemini_key}\n"
    if github_token:
        env_content += f"GITHUB_TOKEN={github_token}\n"
        
    with open(".env", "w") as f:
        f.write(env_content)
    print("✅ .env file created successfully!\n")

    # --- 2. Profile Data Setup ---
    print("--- Profile Data Configuration ---")
    data_dir = "data"
    profile_path = os.path.join(data_dir, "static_profile.yaml")
    example_path = os.path.join(data_dir, "static_profile.example.yaml")
    
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    if not os.path.exists(profile_path):
        if os.path.exists(example_path):
            shutil.copy(example_path, profile_path)
            print(f"✅ Created {profile_path} from template.")
        else:
            # Fallback if example is missing
            with open(profile_path, "w") as f:
                f.write('name: "Your Name"\ngithub_username: "yourusername"\nshowcase_repos: []\n')
            print(f"✅ Created a blank {profile_path}.")
    else:
        print(f"ℹ️ {profile_path} already exists. Skipping creation.")

    # --- 3. Next Steps ---
    print("\n🎉 Setup Complete!")
    print("-" * 40)
    print("Next steps:")
    print("1. Open 'data/static_profile.yaml' and fill in your details.")
    print("2. Run 'python src/main.py' to generate your resume.")
    print("-" * 40)

if __name__ == "__main__":
    main()