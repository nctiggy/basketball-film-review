# Pushing to GitHub - Step by Step Guide

## Option 1: Using the Automated Script (Easiest)

### Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `basketball-film-review`
3. Description: "Web app for basketball coaches to upload games, extract clips, and review film"
4. Choose Public or Private
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click "Create repository"
7. Copy the repository URL (e.g., `https://github.com/yourusername/basketball-film-review.git`)

### Step 2: Run the Setup Script

```bash
cd basketball-film-review
./git-setup.sh
```

The script will:
- Initialize git repository
- Stage all files
- Create initial commit
- Add remote origin
- Push to GitHub

Just follow the prompts and paste your repository URL when asked!

---

## Option 2: Manual Setup

If you prefer to do it manually:

### Step 1: Create GitHub Repository (same as above)

### Step 2: Initialize and Push

```bash
cd basketball-film-review

# Initialize git
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Basketball Film Review application"

# Add your GitHub repository as remote
git remote add origin https://github.com/YOUR-USERNAME/basketball-film-review.git

# Rename branch to main (if needed)
git branch -M main

# Push to GitHub
git push -u origin main
```

---

## Authentication Options

### Option A: HTTPS with Personal Access Token (Recommended)

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a name: "Basketball Film Review"
4. Select scopes: `repo` (Full control of private repositories)
5. Click "Generate token"
6. **Copy the token** (you won't see it again!)
7. When git prompts for password, paste the token (not your GitHub password)

### Option B: SSH (More Secure, Requires Setup)

1. Generate SSH key (if you don't have one):
   ```bash
   ssh-keygen -t ed25519 -C "your-email@example.com"
   ```

2. Add to SSH agent:
   ```bash
   eval "$(ssh-agent -s)"
   ssh-add ~/.ssh/id_ed25519
   ```

3. Copy public key:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```

4. Add to GitHub: Settings → SSH and GPG keys → New SSH key

5. Use SSH URL instead:
   ```bash
   git remote add origin git@github.com:YOUR-USERNAME/basketball-film-review.git
   ```

### Option C: GitHub CLI (If Installed)

```bash
# Login
gh auth login

# Create repository and push
gh repo create basketball-film-review --public --source=. --push
```

---

## Troubleshooting

### "Repository not found"
- Make sure the repository exists on GitHub
- Check you're using the correct URL
- Verify you have access to the repository

### "Authentication failed"
- HTTPS: Use a Personal Access Token, not your password
- SSH: Make sure your SSH key is added to GitHub
- Try `gh auth login` if using GitHub CLI

### "Permission denied"
- Check repository permissions
- Make sure you're the owner or have write access
- For organization repos, check organization settings

### "Updates were rejected"
- The remote has changes you don't have
- Either:
  ```bash
  git pull origin main --rebase
  git push origin main
  ```
  Or force push (careful!):
  ```bash
  git push -f origin main
  ```

---

## After Pushing

### Recommended: Update Repository Settings

1. **Add Topics**: Go to repository → About (gear icon) → Add topics
   - `basketball`, `video-processing`, `kubernetes`, `helm`, `fastapi`, `coaching`, `sports`

2. **Add Description**: 
   > "Web application for basketball coaches to upload games, extract clips with timestamps, and organize film for team review. Kubernetes-ready with Helm deployment."

3. **Set Up Branch Protection** (Settings → Branches):
   - Protect `main` branch
   - Require pull request reviews
   - Require status checks

4. **Add GitHub Actions** (Optional):
   - Docker image builds
   - Helm chart linting
   - Security scanning

5. **Create Releases**:
   - Tag version: `v1.0.0`
   - Add release notes
   - Attach built Docker images

---

## Useful Git Commands for Later

```bash
# Check status
git status

# View commit history
git log --oneline

# Create a new branch
git checkout -b feature/new-feature

# Push new branch
git push -u origin feature/new-feature

# Update from remote
git pull origin main

# Tag a release
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# View remotes
git remote -v
```

---

## Need Help?

- GitHub Docs: https://docs.github.com/
- Git Documentation: https://git-scm.com/doc
- GitHub Support: https://support.github.com/

Your project is ready to share with the world! 🚀
