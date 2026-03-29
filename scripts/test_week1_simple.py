# Week 1 Test - Infrastructure and Basic Framework
import os
import sys
import yaml
import subprocess
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("=" * 70)
print("Week 1 Simple Test - Infrastructure & Basic Framework")
print("=" * 70)

passed = 0
total = 0


def run_test(index: int, name: str, test_func):
    global passed, total

    total += 1
    print(f"\n[{index}/7] Testing {name}...")

    try:
        test_func()
        passed += 1
    except AssertionError as e:
        print(f"FAIL - {e}")
    except Exception as e:
        print(f"FAIL - Error: {e}")


def test_docker_compose_config_exists():
    """Verify Docker Compose configuration file exists."""
    docker_compose_path = os.path.join(PROJECT_ROOT, "docker-compose.yml")
    assert os.path.exists(docker_compose_path), "docker-compose.yml 文件不存在"
    print("OK - docker-compose.yml exists")


def test_docker_compose_valid_syntax():
    """Verify Docker Compose configuration has valid YAML syntax."""
    docker_compose_path = os.path.join(PROJECT_ROOT, "docker-compose.yml")
    with open(docker_compose_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    assert config is not None, "Docker Compose 配置为空"
    assert "services" in config, "Docker Compose 缺少 services 配置"
    print("OK - Docker Compose YAML syntax is valid")


def test_docker_compose_has_required_services():
    """Verify Docker Compose has required services."""
    docker_compose_path = os.path.join(PROJECT_ROOT, "docker-compose.yml")
    with open(docker_compose_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    services = config.get("services", {})
    assert "db" in services or "postgres" in services, "Docker Compose 缺少数据库服务"
    assert "chroma" in services or "chromadb" in services, "Docker Compose 缺少 ChromaDB 服务"
    print("OK - Docker Compose has required services")


def test_dockerfile_exists():
    """Verify Dockerfile exists."""
    dockerfile_path = os.path.join(PROJECT_ROOT, "Dockerfile")
    assert os.path.exists(dockerfile_path), "Dockerfile 文件不存在"
    print("OK - Dockerfile exists")


def test_database_scripts_exist():
    """Verify database initialization scripts exist."""
    data_dir = os.path.join(PROJECT_ROOT, "data")

    # Check for init scripts
    init_scripts = []
    for file in os.listdir(data_dir) if os.path.exists(data_dir) else []:
        if file.startswith("init") and file.endswith(".sql"):
            init_scripts.append(file)

    assert len(init_scripts) > 0, f"未找到数据库初始化脚本（如 init_db.sql），当前目录: {data_dir}"
    print(f"OK - Found {len(init_scripts)} init script(s): {init_scripts}")


def test_seed_data_script_exists():
    """Verify seed data script exists."""
    scripts_dir = os.path.join(PROJECT_ROOT, "scripts")
    seed_script = os.path.join(scripts_dir, "seed_data.py")

    assert os.path.exists(seed_script), "seed_data.py 脚本不存在"
    print("OK - seed_data.py exists")


def test_streamlit_app_exists():
    """Verify Streamlit application file exists."""
    app_path = os.path.join(PROJECT_ROOT, "app.py")
    assert os.path.exists(app_path), "app.py 文件不存在"

    # Check if it's a valid Streamlit app
    with open(app_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "streamlit" in content.lower() or "st." in content, "app.py 不包含 Streamlit 代码"
    print("OK - Streamlit app.py exists and contains Streamlit code")


run_test(1, "Docker Compose Config Exists", test_docker_compose_config_exists)
run_test(2, "Docker Compose Valid Syntax", test_docker_compose_valid_syntax)
run_test(3, "Docker Compose Required Services", test_docker_compose_has_required_services)
run_test(4, "Dockerfile Exists", test_dockerfile_exists)
run_test(5, "Database Scripts Exist", test_database_scripts_exist)
run_test(6, "Seed Data Script Exists", test_seed_data_script_exists)
run_test(7, "Streamlit App Exists", test_streamlit_app_exists)

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print(f"Total: {total}")
print(f"Passed: {passed}")
print(f"Success Rate: {(passed / total * 100) if total else 0:.1f}%")
print("=" * 70)

if passed == total:
    print("\n[SUCCESS] Week 1 infrastructure is ready!")
    sys.exit(0)

print(f"\n[FAILED] {total - passed} tests failed")
sys.exit(1)
