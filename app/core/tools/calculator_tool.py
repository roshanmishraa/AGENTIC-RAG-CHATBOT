# requirements.txt mein add karo: asteval

from asteval import Interpreter

@tool
def calculator_tool(expression: str) -> str:
    """Performs mathematical calculations."""
    try:
        aeval = Interpreter()
        result = aeval(expression)
        if aeval.error:
            return f"Calculation error: {aeval.error[0].get_error()}"
        return str(result)
    except Exception as e:
        return f"Calculation error: {str(e)}"