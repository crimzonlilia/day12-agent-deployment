"""
Production Readiness Checker - My Production Agent
Tự động kiểm tra project có đủ điều kiện deploy chưa.
"""
import os
import sys

def check(name: str, passed: bool, detail: str = "") -> dict:
    icon = "[PASS]" if passed else "[FAIL]"
    print(f"  {icon} {name}" + (f" - {detail}" if detail else ""))
    return {"name": name, "passed": passed}

def run_checks():
    results = []
    base = os.path.dirname(__file__)

    print("\n" + "=" * 55)
    print("  Production Readiness Check - Day 12 Lab")
    print("=" * 55)

    # -- Files ----------------------------------------------------
    print("\n[Files] Checking required files...")
    files = ["Dockerfile", "docker-compose.yml", ".dockerignore", ".env.example", "requirements.txt", "railway.toml"]
    for f in files:
        results.append(check(f"{f} exists", os.path.exists(os.path.join(base, f))))

    # -- Security ----------------------------------------------------
    print("\n[Security] Checking security constraints...")
    gitignore = os.path.join(base, ".gitignore")
    env_ignored = False
    if os.path.exists(gitignore):
        with open(gitignore, encoding="utf-8") as f:
            content = f.read()
            if ".env" in content:
                env_ignored = True
    results.append(check(".env in .gitignore", env_ignored))

    # Check hardcoded secrets
    secrets_found = []
    for f in ["app/main.py", "app/config.py"]:
        fpath = os.path.join(base, f)
        if os.path.exists(fpath):
            with open(fpath, encoding="utf-8") as file:
                content = file.read()
                for bad in ["sk-", "password123", "hardcoded"]:
                    if bad in content:
                        secrets_found.append(f"{f}:{bad}")
    results.append(check("No hardcoded secrets", len(secrets_found) == 0))

    # -- API Logic --------------------------------------------
    print("\n[API] Checking implementation...")
    main_py = os.path.join(base, "app", "main.py")
    if os.path.exists(main_py):
        with open(main_py, encoding="utf-8") as f:
            content = f.read()
            results.append(check("/health endpoint", '"/health"' in content))
            results.append(check("/ready endpoint", '"/ready"' in content))
            results.append(check("Authentication", "api_key" in content.lower() or "verify_token" in content))
            results.append(check("Rate limiting", "rate_limit" in content.lower() or "429" in content))
            results.append(check("Graceful shutdown", "SIGTERM" in content))
            results.append(check("Structured logging", "json.dumps" in content or '"event"' in content))
    
    # -- Docker -----------------------------------------------------
    print("\n[Docker] Checking Dockerfile standards...")
    dockerfile = os.path.join(base, "Dockerfile")
    if os.path.exists(dockerfile):
        with open(dockerfile, encoding="utf-8") as f:
            content = f.read()
            results.append(check("Multi-stage build", "AS builder" in content and "AS runtime" in content))
            results.append(check("Non-root user", "USER agent" in content or "useradd" in content))
            results.append(check("HEALTHCHECK", "HEALTHCHECK" in content))

    # -- Summary ---------------------------------------------------
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print("\n" + "=" * 55)
    print(f"  Result: {passed}/{total} checks passed")
    if passed == total:
        print("  DONE: PRODUCTION READY!")
    print("=" * 55 + "\n")
    return passed == total

if __name__ == "__main__":
    run_checks()
