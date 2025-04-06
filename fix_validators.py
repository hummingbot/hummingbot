#!/usr/bin/env python3

import os
import re
from pathlib import Path

# More comprehensive pattern to find validator methods with problematic signature
# This will catch various forms of the problematic pattern
validator_pattern = re.compile(r'def\s+(validate\w+)\s*\(cls,\s*v(\w*)?(\:\s*\w+)?(,\s*values\s*:\s*Dict)?(\s*,\s*info\s*:\s*Dict\s*=\s*None)?\s*\)')

# Function to fix a file
def fix_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        print(f"Skipping binary file: {file_path}")
        return False
    
    # Check if the file contains problematic validator methods
    matches = validator_pattern.findall(content)
    if not matches:
        return False
    
    print(f"Fixing file: {file_path}")
    print(f"Found {len(matches)} potential validators to fix")
    
    # Replace the problematic validator methods
    for method_name, v_suffix, v_type, values_part, info_part in matches:
        if info_part:  # Only fix if there is an info parameter
            old_signature = f"def {method_name}(cls, v{v_suffix}{v_type}{values_part}{info_part})"
            new_signature = f"def {method_name}(cls, v{v_suffix}{v_type}{values_part})"
            content = content.replace(old_signature, new_signature)
            
            # Remove references to info in the method body
            # Find the method body by looking for the method name and tracking indentation
            method_start = content.find(old_signature)
            if method_start != -1:
                method_lines = []
                lines = content[method_start:].split('\n')
                method_indent = None
                
                # Get the first line's indentation
                for i, line in enumerate(lines):
                    if i == 0:  # First line is the signature
                        continue
                    if line.strip():  # First non-empty line after signature
                        method_indent = len(line) - len(line.lstrip())
                        break
                
                # If we couldn't find the indentation, skip modifying the method body
                if method_indent is None:
                    continue
                
                # Collect all lines of the method
                in_method = True
                for i, line in enumerate(lines):
                    if i == 0:  # Skip the signature line
                        method_lines.append(line)
                        continue
                    
                    # Check if we're still in the method by comparing indentation
                    if line.strip() and len(line) - len(line.lstrip()) <= method_indent:
                        # We've reached a line with less indentation, so we're out of the method
                        if i > 0:  # Make sure we have at least one line of method body
                            in_method = False
                            break
                    
                    if in_method:
                        # Remove references to info parameter
                        if "info" in line:
                            # Replace info.get with a comment
                            line = re.sub(r'(\s+)info\.get\([\'"]([^\'"]+)[\'"]\)(\s+if\s+info\s+else\s+None)', 
                                         r'\1None  # Removed info.get reference', line)
                            # Replace direct info indexing
                            line = re.sub(r'(\s+)info\[[\'"]([^\'"]+)[\'"]\]', 
                                         r'\1None  # Removed info reference', line)
                            # Replace info dictionary access
                            line = re.sub(r'(\s+)info(?:\s*\.)?\s*get\([\'"]([^\'"]+)[\'"]\)', 
                                         r'\1None  # Removed info.get reference', line)
                            # Replace info existence checks
                            line = re.sub(r'(\s+)if\s+info\s+is\s+None:', 
                                         r'\1if True:  # Removed info check', line)
                            line = re.sub(r'(\s+)if\s+info\s*(?:!=|is not)\s*None:', 
                                         r'\1if False:  # Removed info check', line)
                        
                        method_lines.append(line)
                
                # Reconstruct the method
                method_text = '\n'.join(method_lines)
                content = content.replace(content[method_start:method_start+len(method_text)], method_text)
    
    # Write the modified content back to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return True

# Find all Python files and fix them
def fix_all_validators():
    fixed_count = 0
    
    for root, dirs, files in os.walk('.'):
        # Skip hidden directories and virtual environments
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__' and d != '.venv']
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if fix_file(file_path):
                    fixed_count += 1
    
    print(f"Fixed {fixed_count} files")

if __name__ == "__main__":
    fix_all_validators() 