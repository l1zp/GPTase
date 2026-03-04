---
name: symbolic_math
description: |
  Symbolic mathematical computation and LaTeX parsing. Use when analyzing
  equations, verifying derivations, performing symbolic manipulation, or
  explaining mathematical concepts from scientific papers.

  Provides integration with SymPy for symbolic mathematics.

tools:
  - parse_latex
  - verify_derivation
  - symbolic_simplify
  - compute_derivative
  - compute_integral
  - solve_equation
  - expand_expression
  - substitute_values
---

# Symbolic Mathematics Skill

## Overview

This skill provides symbolic mathematical capabilities for analyzing equations and formulas from scientific papers. It integrates SymPy for symbolic computation and supports LaTeX parsing.

## Capabilities

### 1. parse_latex

Parse LaTeX equations into symbolic form.

```python
from sympy import parse_latex

# Parse a LaTeX equation
expr = parse_latex(r"\frac{dE}{dt} = -k \cdot T \cdot \nabla S")

# Returns symbolic expression for further analysis
```

**Parameters:**
- `latex_str`: LaTeX string to parse

**Returns:**
- SymPy expression object

### 2. verify_derivation

Verify mathematical derivation steps.

```python
from sympy import symbols, simplify, Eq

def verify_derivation(steps: list) -> dict:
    """
    Verify a sequence of derivation steps.

    Args:
        steps: List of (from_expr, to_expr, operation) tuples

    Returns:
        Dictionary with verification results for each step
    """
    results = []
    for from_expr, to_expr, operation in steps:
        # Verify the transformation is valid
        simplified = simplify(from_expr - to_expr)
        valid = simplified == 0
        results.append({
            "valid": valid,
            "operation": operation,
            "from": str(from_expr),
            "to": str(to_expr)
        })
    return results
```

**Parameters:**
- `steps`: List of derivation steps to verify

**Returns:**
- Verification results for each step

### 3. symbolic_simplify

Simplify complex mathematical expressions.

```python
from sympy import simplify, trigsimp, expand

def symbolic_simplify(expr, method="auto"):
    """
    Simplify mathematical expression.

    Args:
        expr: SymPy expression
        method: 'auto', 'algebraic', 'trigonometric', 'rational'

    Returns:
        Simplified expression
    """
    if method == "trigonometric":
        return trigsimp(expr)
    elif method == "rational":
        return expr.rational_simplify()
    else:
        return simplify(expr)
```

**Parameters:**
- `expr`: Expression to simplify
- `method`: Simplification method

**Returns:**
- Simplified expression

### 4. compute_derivative

Compute symbolic derivatives.

```python
from sympy import diff, symbols

def compute_derivative(expr, var, order=1):
    """
    Compute derivative of expression with respect to variable.

    Args:
        expr: SymPy expression
        var: Variable to differentiate with respect to
        order: Order of derivative (default 1)

    Returns:
        Derivative expression
    """
    return diff(expr, var, order)
```

**Parameters:**
- `expr`: Expression to differentiate
- `var`: Variable for differentiation
- `order`: Order of derivative

**Returns:**
- Derivative expression

### 5. compute_integral

Compute symbolic integrals.

```python
from sympy import integrate, symbols

def compute_integral(expr, var, limits=None):
    """
    Compute integral of expression.

    Args:
        expr: SymPy expression
        var: Variable to integrate with respect to
        limits: Optional (lower, upper) for definite integral

    Returns:
        Integral result
    """
    if limits:
        return integrate(expr, (var, limits[0], limits[1]))
    return integrate(expr, var)
```

**Parameters:**
- `expr`: Expression to integrate
- `var`: Variable for integration
- `limits`: Optional integration limits

**Returns:**
- Integral result

### 6. solve_equation

Solve equations symbolically.

```python
from sympy import solve, Eq

def solve_equation(expr, var):
    """
    Solve equation for variable.

    Args:
        expr: Equation (can be Eq object or expression = 0)
        var: Variable to solve for

    Returns:
        List of solutions
    """
    return solve(expr, var)
```

**Parameters:**
- `expr`: Equation to solve
- `var`: Variable to solve for

**Returns:**
- List of solutions

## Usage Examples

### Example 1: Analyzing a Loss Function

```python
# Parse cross-entropy loss
loss = parse_latex(r"L = -\sum_{i} y_i \log(\hat{y}_i)")

# Compute derivative with respect to predictions
from sympy import symbols, log
y, y_hat = symbols('y y_hat', positive=True)
L = -y * log(y_hat)
dL_dy_hat = diff(L, y_hat)
# Result: -y/y_hat
```

### Example 2: Verifying Gradient Descent Update

```python
from sympy import symbols

theta, alpha, grad = symbols('theta alpha grad')
update = theta - alpha * grad

# Verify this minimizes a quadratic loss
# L = 0.5 * theta^2
# dL/dtheta = theta
# update = theta - alpha * theta = theta(1 - alpha)
```

### Example 3: Simplifying a Complex Expression

```python
from sympy import parse_latex, simplify

expr = parse_latex(r"\frac{x^2 - 1}{x - 1}")
simplified = simplify(expr)
# Result: x + 1
```

## Dependencies

This skill requires the following Python packages:

```
sympy>=1.12
antlr4-python3-runtime>=4.11  # For LaTeX parsing
```

## Installation

```bash
pip install sympy antlr4-python3-runtime
```

## Notes

- LaTeX parsing may not support all LaTeX constructs
- Complex derivations may require manual guidance
- Some operations may be computationally expensive for very large expressions
