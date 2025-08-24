
class CalculatorService:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

    def multiply(self, a, b):
        return a * b

    def divide(self, a, b):
        if b == 0:
            raise ValueError("Cannot divide by zero.")
        return a / b
    
    def Average(self, numbers):
        if not numbers:
            raise ValueError("The list of numbers is empty.")
        return sum(numbers) / len(numbers)