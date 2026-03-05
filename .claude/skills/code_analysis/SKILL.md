---
name: code_analysis
description: |
  Multi-language code analysis for understanding algorithm implementations from research paper repositories.
  Use this skill whenever the user needs to analyze code structure, trace data flow, extract API calls, map code to mathematical formulas, or understand research code implementations.
  Triggers on: "analyze this code", "understand this implementation", "trace data flow", "map code to paper", "code structure analysis", "extract API calls", "what does this code do", "analyze the algorithm", "PyTorch model analysis", "TensorFlow code".
---

# Code Analysis

Multi-language code analysis for understanding algorithm implementations from research paper repositories. Supports Python, PyTorch, TensorFlow, C++, CUDA, and MATLAB.

## Overview

This skill provides deep code analysis capabilities for research repositories. It supports multiple programming languages and frameworks commonly used in scientific computing and machine learning research.

## Supported Languages

| Language | Frameworks | Analysis Depth |
|----------|------------|----------------|
| Python | PyTorch, TensorFlow, JAX, NumPy, SciPy | Full |
| C++ | CUDA, STL | Structure + Data Flow |
| MATLAB | Standard library | Structure |
| Julia | Flux, Zygote | Structure |

## Capabilities

### 1. analyze_structure

Analyze code organization and identify key components.

```python
import ast
from pathlib import Path

def analyze_structure(code_path: str) -> dict:
    """
    Analyze code structure and organization.

    Args:
        code_path: Path to Python file or directory

    Returns:
        Dictionary with:
        - entry_points: List of main functions/scripts
        - classes: List of class definitions with methods
        - functions: List of function definitions
        - imports: List of imported modules
        - call_graph: Function call relationships
    """
    result = {
        "entry_points": [],
        "classes": [],
        "functions": [],
        "imports": [],
        "call_graph": {}
    }

    # Parse Python file
    with open(code_path, 'r') as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            result["functions"].append({
                "name": node.name,
                "args": [arg.arg for arg in node.args.args],
                "line": node.lineno
            })
        elif isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
            result["classes"].append({
                "name": node.name,
                "methods": methods,
                "line": node.lineno
            })
        elif isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)

    return result
```

**Parameters:**
- `code_path`: Path to code file or directory

**Returns:**
- Structure analysis dictionary

### 2. trace_data_flow

Trace data transformations through code.

```python
def trace_data_flow(entry_point: str, code_path: str) -> dict:
    """
    Trace how data flows from input to output.

    Args:
        entry_point: Function name to start tracing
        code_path: Path to code file

    Returns:
        Dictionary with:
        - input_schema: Expected input types/shapes
        - transformations: List of transformation stages
        - output_schema: Output types/shapes
    """
    # Analyze the function and its callees
    # Track variable assignments and transformations
    pass
```

**Parameters:**
- `entry_point`: Entry function name
- `code_path`: Path to code file

**Returns:**
- Data flow analysis

### 3. extract_api_calls

Identify library and framework usage patterns.

```python
def extract_api_calls(code_path: str, framework: str = None) -> dict:
    """
    Extract API calls to understand library usage.

    Args:
        code_path: Path to code file
        framework: Optional filter for specific framework (pytorch, tensorflow, etc.)

    Returns:
        Dictionary with:
        - apis: List of API calls with frequency
        - patterns: Common usage patterns
        - deprecated: Potentially deprecated usage
    """
    framework_apis = {
        "pytorch": ["torch.nn", "torch.optim", "torch.utils.data"],
        "tensorflow": ["tf.keras", "tf.data", "tf.train"],
        "numpy": ["np.array", "np.linalg", "np.fft"]
    }

    # Parse and extract API calls
    result = {"apis": [], "patterns": [], "deprecated": []}

    with open(code_path, 'r') as f:
        content = f.read()
        tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Extract the function being called
            if isinstance(node.func, ast.Attribute):
                module = node.func.value.id if isinstance(node.func.value, ast.Name) else ""
                func = node.func.attr
                result["apis"].append(f"{module}.{func}")

    return result
```

**Parameters:**
- `code_path`: Path to code file
- `framework`: Optional framework filter

**Returns:**
- API usage analysis

### 4. map_to_math

Connect code implementations to mathematical formulations.

```python
def map_to_math(code_path: str, formulas: list) -> dict:
    """
    Map code to mathematical formulas from paper.

    Args:
        code_path: Path to code file
        formulas: List of formula descriptions from paper

    Returns:
        Dictionary mapping code locations to formulas
    """
    # Common patterns for formula implementation
    patterns = {
        "matrix_multiply": ["matmul", "mm", "dot", "@"],
        "attention": ["attention", "softmax", "scaled_dot"],
        "normalization": ["layer_norm", "batch_norm", "normalize"],
        "activation": ["relu", "gelu", "sigmoid", "tanh"],
        "loss": ["cross_entropy", "mse", "loss"]
    }

    mappings = []
    # Match code patterns to formula types
    return mappings
```

**Parameters:**
- `code_path`: Path to code file
- `formulas`: List of formula descriptions

**Returns:**
- Code-to-formula mappings

### 5. find_patterns

Identify common algorithmic patterns.

```python
def find_patterns(code_path: str) -> dict:
    """
    Identify common algorithmic and design patterns.

    Args:
        code_path: Path to code file

    Returns:
        Dictionary with:
        - design_patterns: Singleton, Factory, Strategy, etc.
        - ml_patterns: Training loop, Attention, Residual, etc.
        - optimization_patterns: Gradient clipping, Learning rate scheduling
    """
    ml_patterns = {
        "training_loop": ["for epoch", "optimizer.step", "loss.backward"],
        "attention": ["query", "key", "value", "softmax"],
        "residual": ["x + ", "+ x", "residual"],
        "normalization": ["layer_norm", "batch_norm", "instance_norm"],
        "regularization": ["dropout", "weight_decay", "l2"]
    }

    found_patterns = []

    with open(code_path, 'r') as f:
        content = f.read().lower()

    for pattern_name, keywords in ml_patterns.items():
        if any(kw.lower() in content for kw in keywords):
            found_patterns.append(pattern_name)

    return {"patterns": found_patterns}
```

**Parameters:**
- `code_path`: Path to code file

**Returns:**
- Found patterns

### 6. extract_config

Extract hyperparameters and configurations.

```python
def extract_config(code_path: str) -> dict:
    """
    Extract hyperparameters and configuration values.

    Args:
        code_path: Path to code file

    Returns:
        Dictionary with:
        - hyperparameters: Learning rate, batch size, etc.
        - model_config: Layer sizes, hidden dimensions, etc.
        - training_config: Epochs, optimizers, schedulers
    """
    config = {
        "hyperparameters": {},
        "model_config": {},
        "training_config": {}
    }

    # Common hyperparameter patterns
    hp_patterns = {
        "learning_rate": ["lr", "learning_rate", "lr="],
        "batch_size": ["batch_size", "batch="],
        "epochs": ["epochs", "n_epochs", "num_epochs"],
        "hidden_size": ["hidden_size", "d_model", "hidden_dim"],
        "num_layers": ["num_layers", "n_layers", "depth"]
    }

    with open(code_path, 'r') as f:
        content = f.read()

    # Extract values using AST or regex
    # ...

    return config
```

**Parameters:**
- `code_path`: Path to code file

**Returns:**
- Configuration dictionary

## Usage Examples

### Example 1: Analyzing a PyTorch Model

```python
# Analyze structure of a transformer model
structure = analyze_structure("models/transformer.py")
# Returns:
# {
#   "classes": [
#     {"name": "TransformerEncoder", "methods": ["forward", "__init__"]},
#     {"name": "MultiHeadAttention", "methods": ["forward", "__init__"]}
#   ],
#   "imports": ["torch", "torch.nn", "math"]
# }

# Find patterns
patterns = find_patterns("models/transformer.py")
# Returns:
# {"patterns": ["attention", "residual", "normalization"]}
```

### Example 2: Tracing Data Flow

```python
# Trace how input flows through the model
flow = trace_data_flow("forward", "models/transformer.py")
# Returns:
# {
#   "input_schema": {"shape": "[batch, seq_len, d_model]", "type": "tensor"},
#   "transformations": [
#     {"stage": 1, "name": "Self-Attention", "output_shape": "[batch, seq_len, d_model]"},
#     {"stage": 2, "name": "Feed-Forward", "output_shape": "[batch, seq_len, d_model]"}
#   ]
# }
```

### Example 3: Mapping Code to Paper

```python
# Map code to paper equations
formulas = [
    {"id": "F1", "description": "scaled dot-product attention"},
    {"id": "F2", "description": "feed-forward network"}
]

mappings = map_to_math("models/transformer.py", formulas)
# Returns:
# [
#   {"formula": "F1", "code": "MultiHeadAttention.forward", "line": 78},
#   {"formula": "F2", "code": "FeedForward.forward", "line": 120}
# ]
```

## Dependencies

This skill requires the following Python packages:

```
# Core
tree-sitter>=0.20  # Multi-language parsing
tree-sitter-python>=0.20

# Optional (for specific frameworks)
torch>=2.0  # PyTorch model analysis
tensorflow>=2.12  # TensorFlow model analysis
```

## Installation

```bash
pip install tree-sitter tree-sitter-python
```

## Notes

- Python analysis uses the built-in `ast` module
- Multi-language support requires tree-sitter grammars
- Deep learning model analysis requires framework to be installed
- Large codebases may require chunked analysis
