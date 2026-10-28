import os
import re
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
ORIGINAL_PATH = os.environ.setdefault("RBL4_ORIGINAL_PATH", os.environ.get("PATH", ""))


def normalize_java_major(java_version):
    if java_version is None or str(java_version).strip() == "":
        return 8
    value = str(java_version).strip().lower()
    if value.startswith("1."):
        value = value.split(".", 1)[1]
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else 8


def _candidate_dirs():
    seen = set()
    for key in [
        "JAVA_HOME_5",
        "JAVA_HOME_6",
        "JAVA_HOME_7",
        "JAVA_HOME_8",
        "JAVA_HOME_11",
        "JAVA_HOME_17",
        "JAVA_HOME_21",
        "JAVA_HOME_24",
        "JAVA_HOME_25",
        "JAVA_HOME_26",
        "JAVA_HOME_DEFAULT",
        "JAVA_HOME",
    ]:
        value = os.getenv(key)
        if value and value not in seen:
            seen.add(value)
            yield Path(value)

    for root in [Path("C:/Program Files/Eclipse Adoptium"), Path("C:/Program Files/Java")]:
        if root.exists():
            for child in root.iterdir():
                if child.is_dir() and child not in seen:
                    seen.add(str(child))
                    yield child


def _java_major(java_home):
    java = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
    if not java.exists():
        return None
    try:
        result = subprocess.run([str(java), "-version"], capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    text = result.stderr or result.stdout
    match = re.search(r'version "([^"]+)"', text)
    if not match:
        return None
    return normalize_java_major(match.group(1))


def discover_jdks():
    jdks = {}
    for candidate in _candidate_dirs():
        major = _java_major(candidate)
        if major is not None and major not in jdks:
            jdks[major] = str(candidate)
    return dict(sorted(jdks.items()))


def configure_java_home_env():
    jdks = discover_jdks()
    for major, home in jdks.items():
        os.environ.setdefault(f"JAVA_HOME_{major}", home)
    if 8 in jdks:
        os.environ.setdefault("JAVA_HOME_5", jdks[8])
        os.environ.setdefault("JAVA_HOME_6", jdks[8])
        os.environ.setdefault("JAVA_HOME_7", jdks[8])
        os.environ.setdefault("JAVA_HOME_8", jdks[8])
    if jdks:
        os.environ.setdefault("JAVA_HOME_DEFAULT", jdks[max(jdks)])
    return jdks


def select_jdk(java_version=None, min_major=8):
    jdks = configure_java_home_env()
    requested = max(normalize_java_major(java_version), min_major)
    if requested in jdks:
        return requested, jdks[requested]
    higher = [major for major in jdks if major > requested]
    if higher:
        major = min(higher)
        return major, jdks[major]
    lower = [major for major in jdks if major >= min_major]
    if lower:
        major = max(lower)
        return major, jdks[major]
    if jdks:
        major = max(jdks)
        return major, jdks[major]
    return requested, None


def build_java_env(java_version=None, min_major=8):
    major, java_home = select_jdk(java_version, min_major=min_major)
    env = os.environ.copy()
    if java_home:
        java_bin = str(Path(java_home) / "bin")
        sep = ";" if os.name == "nt" else ":"
        env["JAVA_HOME"] = java_home
        env["PATH"] = java_bin + sep + ORIGINAL_PATH
    env["RBL4_ACTIVE_JAVA_VERSION"] = str(java_version or "")
    env["RBL4_ACTIVE_JDK_MAJOR"] = str(major)
    if java_home:
        env["RBL4_ACTIVE_JAVA_HOME"] = java_home
    return env


def activate_java_home(java_version=None, min_major=8):
    env = build_java_env(java_version, min_major=min_major)
    for key in ["JAVA_HOME", "PATH", "RBL4_ACTIVE_JAVA_VERSION", "RBL4_ACTIVE_JDK_MAJOR", "RBL4_ACTIVE_JAVA_HOME"]:
        if key in env:
            os.environ[key] = env[key]
    return os.environ.get("JAVA_HOME")


def describe(java_version=None, min_major=8):
    major, java_home = select_jdk(java_version, min_major=min_major)
    return f"requested={java_version or 'default'} selected_jdk={major} java_home={java_home or 'system-default'}"


def evosuite_jar():
    for path in [BASE_DIR / "evosuite-1.2.0.jar", BASE_DIR / "AgoneTest" / "evosuite-1.2.0.jar"]:
        if path.exists():
            return str(path)
    return str(BASE_DIR / "evosuite-1.2.0.jar")


def evosuite_runtime_jar():
    for path in [BASE_DIR / "evosuite-standalone-runtime-1.2.0.jar", BASE_DIR / "AgoneTest" / "evosuite-standalone-runtime-1.2.0.jar"]:
        if path.exists():
            return str(path)
    return str(BASE_DIR / "evosuite-standalone-runtime-1.2.0.jar")
