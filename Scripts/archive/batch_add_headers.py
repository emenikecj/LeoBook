"""
batch_add_headers.py: One-time script to add/update standardized file headers.
Scans all Python and Dart files in the LeoBook project and adds a standardized
description header to each file based on its contents (functions, classes, imports).

Usage: python Scripts/archive/batch_add_headers.py
"""
import os
import re
import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DART_LIB = PROJECT_ROOT / "leobookapp" / "lib"

# Component mapping for Python files
PY_COMPONENT_MAP = {
    "Core/System": "Core — System",
    "Core/Utils": "Core — Utilities",
    "Core/Intelligence": "Core — Intelligence (AI Engine)",
    "Core/Browser": "Core — Browser Automation",
    "Core/Browser/Extractors": "Core — Browser Extractors",
    "Data/Access": "Data — Access Layer",
    "Data/Supabase": "Data — Supabase Migrations",
    "Modules/Flashscore": "Modules — Flashscore",
    "Modules/FootballCom": "Modules — Football.com",
    "Modules/FootballCom/booker": "Modules — Football.com Booking",
    "Modules/Data": "Modules — Data Processing",
    "Scripts": "Scripts — Pipeline",
}

# Component mapping for Dart files
DART_COMPONENT_MAP = {
    "core/animations": "App — Animations",
    "core/config": "App — Configuration",
    "core/constants": "App — Constants",
    "core/theme": "App — Theme",
    "core/utils": "App — Utilities",
    "core/widgets": "App — Core Widgets",
    "data/models": "App — Data Models",
    "data/repositories": "App — Repositories",
    "data/services": "App — Services",
    "logic/cubit": "App — State Management (Cubit)",
    "presentation/screens": "App — Screens",
    "presentation/screens/rule_engine": "App — Rule Engine Screens",
    "presentation/widgets": "App — Widgets",
    "presentation/widgets/league_tabs": "App — League Tab Widgets",
    "presentation/widgets/responsive": "App — Responsive Widgets",
}


def get_component(filepath: str, mapping: dict) -> str:
    """Get the component label for a file based on its relative path."""
    rel = filepath.replace("\\", "/")
    # Find longest matching prefix
    best = "Unknown"
    best_len = 0
    for prefix, label in mapping.items():
        if prefix in rel and len(prefix) > best_len:
            best = label
            best_len = len(prefix)
    return best


def extract_py_info(filepath: str) -> dict:
    """Extract function names, class names from a Python file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception:
        return {"functions": [], "classes": [], "description": ""}

    functions = []
    classes = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            functions.append(node.name + "()")
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)

    # Try to extract first docstring or comment as description
    description = ""
    lines = source.split("\n")
    for line in lines[:5]:
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("#!"):
            # Extract description from existing comment
            desc = stripped.lstrip("# ").strip()
            if desc and not desc.startswith("---") and len(desc) > 10:
                description = desc
                break

    return {"functions": functions, "classes": classes, "description": description}


def extract_dart_info(filepath: str) -> dict:
    """Extract widget/class names from a Dart file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception:
        return {"classes": [], "description": ""}

    classes = re.findall(r"class\s+(\w+)", source)
    
    # Try to get existing description
    description = ""
    lines = source.split("\n")
    for line in lines[:5]:
        stripped = line.strip()
        if stripped.startswith("///") and len(stripped) > 5:
            desc = stripped.lstrip("/ ").strip()
            if desc:
                description = desc
                break
        elif stripped.startswith("//") and not stripped.startswith("///"):
            desc = stripped.lstrip("/ ").strip()
            if desc and len(desc) > 10:
                description = desc
                break

    return {"classes": classes, "description": description}


def build_py_header(filename: str, component: str, info: dict) -> str:
    """Build a standardized Python header."""
    desc = info.get("description", "")
    if not desc:
        desc = f"{filename}: Module for {component}."
    elif not desc.startswith(filename.replace('.py', '')):
        # Prepend filename if not already there
        pass  # Keep existing description

    lines = [f"# {filename}: {desc}"]
    lines.append(f"# Part of LeoBook {component}")
    lines.append("#")

    funcs = info.get("functions", [])
    classes = info.get("classes", [])
    if classes:
        lines.append(f"# Classes: {', '.join(classes[:8])}")
    if funcs:
        # Cap at 8 functions to keep header concise
        func_str = ", ".join(funcs[:8])
        if len(funcs) > 8:
            func_str += f" (+{len(funcs) - 8} more)"
        lines.append(f"# Functions: {func_str}")

    return "\n".join(lines)


def build_dart_header(filename: str, component: str, info: dict) -> str:
    """Build a standardized Dart header."""
    desc = info.get("description", "")
    if not desc:
        desc = f"{filename}: Widget/screen for {component}."

    lines = [f"/// {filename}: {desc}"]
    lines.append(f"/// Part of LeoBook {component}")

    classes = info.get("classes", [])
    if classes:
        lines.append(f"///")
        lines.append(f"/// Classes: {', '.join(classes[:6])}")

    return "\n".join(lines)


def strip_existing_header(source: str, is_dart: bool) -> str:
    """Remove existing header comments (contiguous block at top of file)."""
    lines = source.split("\n")
    start_idx = 0
    
    if is_dart:
        # Skip leading dart doc comments (///) and regular comments (//)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("///") or stripped.startswith("//") or stripped == "":
                start_idx = i + 1
            else:
                break
    else:
        # Skip leading # comments and empty lines
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#") or stripped == "":
                start_idx = i + 1
            else:
                break

    return "\n".join(lines[start_idx:])


def process_python_files():
    """Process all Python files in the project."""
    count = 0
    skip_dirs = {"__pycache__", "archive", ".venv", "venv", ".git", "build"}
    
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        rel_root = os.path.relpath(root, PROJECT_ROOT)
        
        # Skip non-source directories
        if rel_root.startswith("leobookapp"):
            continue
        
        for fname in files:
            if not fname.endswith(".py"):
                continue
            if fname == "__init__.py":
                continue  # Skip init files
            
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, PROJECT_ROOT)
            component = get_component(rel_path, PY_COMPONENT_MAP)
            info = extract_py_info(fpath)
            
            header = build_py_header(fname, component, info)
            
            with open(fpath, "r", encoding="utf-8") as f:
                source = f.read()
            
            body = strip_existing_header(source, is_dart=False)
            new_content = header + "\n\n" + body
            
            with open(fpath, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_content)
            
            count += 1
            print(f"  [py] {rel_path}")
    
    return count


def process_dart_files():
    """Process all Dart files in lib/."""
    count = 0
    
    if not DART_LIB.exists():
        print("[SKIP] Dart lib directory not found.")
        return 0
    
    for root, dirs, files in os.walk(DART_LIB):
        for fname in files:
            if not fname.endswith(".dart"):
                continue
            
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, DART_LIB)
            component = get_component(rel_path, DART_COMPONENT_MAP)
            info = extract_dart_info(fpath)
            
            header = build_dart_header(fname, component, info)
            
            with open(fpath, "r", encoding="utf-8") as f:
                source = f.read()
            
            body = strip_existing_header(source, is_dart=True)
            new_content = header + "\n\n" + body
            
            with open(fpath, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_content)
            
            count += 1
            print(f"  [dart] {rel_path}")
    
    return count


if __name__ == "__main__":
    print("=" * 60)
    print("  BATCH FILE HEADER UPDATER")
    print("=" * 60)
    
    py_count = process_python_files()
    print(f"\n[DONE] Updated {py_count} Python files.\n")
    
    dart_count = process_dart_files()
    print(f"\n[DONE] Updated {dart_count} Dart files.\n")
    
    print(f"TOTAL: {py_count + dart_count} files updated.")
