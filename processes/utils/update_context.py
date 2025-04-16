"""
Context Update Utility
--------------------
Utility for managing and updating context information during document processing.
Handles state management, progress tracking, and error recovery.

Key Features:
- Context state management
- Progress tracking
- Error state handling
- Checkpoint creation/restoration
- Data persistence

Dependencies:
- json: Data serialization
- logging: Logging functionality
- pathlib: Path handling

Usage:
    from processes.utils.update_context import ContextManager
    
    context = ContextManager()
    context.update_progress("company_name", "status")
    context.save_checkpoint()
"""

import os
import ast
import logging
from pathlib import Path
from typing import Dict, List, Set
import re

class CodebaseContextUpdater:
    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir)
        self.logger = logging.getLogger(__name__)
        self.context_file = self.root_dir / "docs" / "codebase_context.md"
        self.dependencies: Dict[str, Set[str]] = {}
        self.used_by: Dict[str, Set[str]] = {}
        self.key_methods: Dict[str, List[str]] = {}
        
    def analyze_python_file(self, file_path: Path) -> None:
        """Analyze a Python file for dependencies and key methods"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the file
            tree = ast.parse(content)
            
            # Get module name
            module_name = file_path.stem
            
            # Initialize sets for this module
            self.dependencies[module_name] = set()
            self.used_by[module_name] = set()
            self.key_methods[module_name] = []
            
            # Analyze imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        self.dependencies[module_name].add(name.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        self.dependencies[module_name].add(node.module.split('.')[0])
                
                # Find key methods (those with docstrings)
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    if ast.get_docstring(node):
                        self.key_methods[module_name].append(node.name)
            
            # Look for usage patterns in the code
            content_lower = content.lower()
            for other_module in self.dependencies.keys():
                if other_module != module_name:
                    if re.search(rf'\b{other_module}\b', content):
                        self.used_by[other_module].add(module_name)
                        
        except Exception as e:
            self.logger.error(f"Error analyzing {file_path}: {e}")
    
    def analyze_codebase(self) -> None:
        """Analyze all Python files in the codebase"""
        for root, _, files in os.walk(self.root_dir):
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    self.analyze_python_file(file_path)
    
    def generate_context_md(self) -> str:
        """Generate the context documentation"""
        md = ["# Codebase Context\n"]
        
        # Core Components section
        md.append("## Core Components\n")
        
        for module in sorted(self.dependencies.keys()):
            md.append(f"### {module} ({self._get_file_path(module)})\n")
            md.append(f"- **Primary Role**: {self._get_primary_role(module)}\n")
            
            # Dependencies
            if self.dependencies[module]:
                md.append("- **Key Dependencies**:\n")
                for dep in sorted(self.dependencies[module]):
                    md.append(f"  - {dep}\n")
            
            # Used By
            if module in self.used_by:
                md.append("- **Used By**:\n")
                for user in sorted(self.used_by[module]):
                    md.append(f"  - {user}\n")
            
            # Key Methods
            if self.key_methods[module]:
                md.append("- **Key Methods**:\n")
                for method in sorted(self.key_methods[module]):
                    md.append(f"  - `{method}()`\n")
            
            md.append("\n")
        
        # Common Patterns section
        md.append("## Common Patterns\n")
        md.append("### 1. Company Processing\n")
        md.append("- Always use CompanyListHandler for company filtering\n")
        md.append("- Extend existing filtering methods\n")
        md.append("- Never create new company processing scripts\n\n")
        
        md.append("### 2. Document Processing\n")
        md.append("- Use ESMAScraper for all ESMA interactions\n")
        md.append("- Maintain download cache\n")
        md.append("- Follow established error handling\n\n")
        
        # State Management section
        md.append("## State Management\n")
        md.append("### 1. Company State\n")
        md.append("- Location: company_progress.json\n")
        md.append("- Managed by: CompanyListHandler\n")
        md.append("- Updated: After each company processed\n\n")
        
        return "".join(md)
    
    def _get_file_path(self, module: str) -> str:
        """Get the file path for a module"""
        for root, _, files in os.walk(self.root_dir):
            for file in files:
                if file == f"{module}.py":
                    return str(Path(root) / file)
        return "Unknown"
    
    def _get_primary_role(self, module: str) -> str:
        """Get the primary role of a module based on its name and dependencies"""
        roles = {
            "company_list_handler": "Company data management and filtering",
            "esma_scraper": "ESMA website interaction and document downloading",
            "pdf_extractor": "PDF data extraction and processing",
            "extract_bank_info": "Bank information processing and analysis",
            "main": "Main execution and orchestration"
        }
        return roles.get(module, "Unknown role")
    
    def update_context(self) -> None:
        """Update the context documentation"""
        try:
            # Create docs directory if it doesn't exist
            self.context_file.parent.mkdir(exist_ok=True)
            
            # Analyze codebase
            self.analyze_codebase()
            
            # Generate new context
            new_context = self.generate_context_md()
            
            # Write to file
            with open(self.context_file, 'w', encoding='utf-8') as f:
                f.write(new_context)
            
            self.logger.info(f"Updated context documentation at {self.context_file}")
            
        except Exception as e:
            self.logger.error(f"Error updating context: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    updater = CodebaseContextUpdater()
    updater.update_context() 