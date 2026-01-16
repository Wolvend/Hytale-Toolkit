#!/usr/bin/env python3
"""Fix decompilation artifacts in decompiled Java source files."""

import os
import re
import sys

def fix_file(filepath):
    """Fix a single Java file. Returns True if modifications were made."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
        return False

    original = content

    # Replace <unrepresentable> with a valid Java identifier
    # This token appears where the decompiler couldn't resolve a class name
    content = content.replace('<unrepresentable>', 'DecompilerPlaceholder')

    # Replace $assertionsDisabled references with false
    # These are assertion-related checks that aren't meaningful in decompiled code
    content = re.sub(r'DecompilerPlaceholder\.\$assertionsDisabled', 'false', content)

    # Fix interfaces with static initializer blocks (not valid Java)
    # Check if this is an interface
    if re.search(r'^public\s+interface\s+\w+', content, re.MULTILINE):
        # Find CODEC field declaration without initialization
        codec_match = re.search(r'(BuilderCodecMapCodec<[^>]+>)\s+CODEC\s*;', content)
        if codec_match:
            # Find the initialization in the static block
            init_match = re.search(r'CODEC\s*=\s*(new\s+BuilderCodecMapCodec<>\([^)]*\))\s*;', content)
            if init_match:
                # Replace uninitialized field with initialized one
                content = re.sub(
                    r'(BuilderCodecMapCodec<[^>]+>)\s+CODEC\s*;',
                    f'\\1 CODEC = {init_match.group(1)};',
                    content
                )

        # Remove static blocks from interfaces (they're not allowed)
        # Match static { ... } blocks - be careful with nested braces
        lines = content.split('\n')
        new_lines = []
        in_static_block = False
        brace_count = 0

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('static {') or stripped == 'static {':
                in_static_block = True
                brace_count = line.count('{') - line.count('}')
                continue

            if in_static_block:
                brace_count += line.count('{') - line.count('}')
                if brace_count <= 0:
                    in_static_block = False
                continue

            new_lines.append(line)

        content = '\n'.join(new_lines)

    if content != original:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"  Error writing {filepath}: {e}")
            return False

    return False

def main():
    decompiled_dir = 'decompiled'

    if not os.path.isdir(decompiled_dir):
        print(f"Error: '{decompiled_dir}' directory not found.")
        print("Run this script from the Hytale-Toolkit root directory.")
        sys.exit(1)

    print("Fixing assertion tokens in decompiled source...")

    count = 0
    for root, dirs, files in os.walk(decompiled_dir):
        for filename in files:
            if filename.endswith('.java'):
                filepath = os.path.join(root, filename)
                if fix_file(filepath):
                    # Show relative path from decompiled/
                    relpath = os.path.relpath(filepath, decompiled_dir)
                    print(f"  Fixed: {relpath}")
                    count += 1

    print()
    print(f"Fixed {count} files")
    if count > 0:
        print("You can now run javadoc successfully!")
    else:
        print("No files needed fixing.")

if __name__ == '__main__':
    main()
