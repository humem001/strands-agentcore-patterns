#!/usr/bin/env python3
"""
Validate CloudFormation template syntax and structure.
"""
import sys
import yaml
from pathlib import Path


# Add CloudFormation intrinsic function constructors
def cloudformation_constructor(loader, tag_suffix, node):
    """Handle CloudFormation intrinsic functions like !Ref, !GetAtt, etc."""
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return None


# Register CloudFormation intrinsic functions
yaml.add_multi_constructor('!', cloudformation_constructor, Loader=yaml.SafeLoader)


def validate_template(template_path: str) -> bool:
    """
    Validate CloudFormation template.
    
    Args:
        template_path: Path to CloudFormation template file
        
    Returns:
        True if valid, False otherwise
    """
    try:
        with open(template_path, 'r') as f:
            template = yaml.safe_load(f)
        
        # Check required top-level keys
        required_keys = ['AWSTemplateFormatVersion', 'Description', 'Resources']
        for key in required_keys:
            if key not in template:
                print(f"ERROR: Missing required key: {key}")
                return False
        
        # Check Resources section
        if not isinstance(template['Resources'], dict):
            print("ERROR: Resources must be a dictionary")
            return False
        
        if len(template['Resources']) == 0:
            print("ERROR: Resources section is empty")
            return False
        
        # Check Outputs section if present
        if 'Outputs' in template:
            if not isinstance(template['Outputs'], dict):
                print("ERROR: Outputs must be a dictionary")
                return False
        
        print(f"✓ Template is valid YAML")
        print(f"✓ Contains {len(template['Resources'])} resources")
        if 'Outputs' in template:
            print(f"✓ Contains {len(template['Outputs'])} outputs")
        
        return True
        
    except yaml.YAMLError as e:
        print(f"ERROR: Invalid YAML syntax: {e}")
        return False
    except FileNotFoundError:
        print(f"ERROR: Template file not found: {template_path}")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        return False


if __name__ == '__main__':
    template_path = Path(__file__).parent / 'cloudformation-template.yaml'
    
    if len(sys.argv) > 1:
        template_path = Path(sys.argv[1])
    
    success = validate_template(str(template_path))
    sys.exit(0 if success else 1)
