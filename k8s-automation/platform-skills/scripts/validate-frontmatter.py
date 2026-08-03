#!/usr/bin/env python3
import sys
import yaml

REQUIRED_FIELDS = ['name', 'description', 'status', 'layer']

def validate(filepath):
    with open(filepath) as f:
        content = f.read()
    if not content.startswith('---'):
        print(f"FAIL {filepath}: missing frontmatter")
        sys.exit(1)
    parts = content.split('---', 2)
    if len(parts) < 3:
        print(f"FAIL {filepath}: malformed frontmatter")
        sys.exit(1)
    fm = yaml.safe_load(parts[1])
    for field in REQUIRED_FIELDS:
        if field not in fm or not fm[field]:
            print(f"FAIL {filepath}: missing required field '{field}'")
            sys.exit(1)
    print(f"OK   {filepath}")

if __name__ == '__main__':
    validate(sys.argv[1])
