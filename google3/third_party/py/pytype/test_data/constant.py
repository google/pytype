"""Test constant folding."""
# Unhashable type, will raise an error in constant folding
x = {[1, 2]}
