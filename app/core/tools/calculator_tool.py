from langchain_core.tools import tool



@tool
def calculator_tool(
    expression:str
)->str:

    """
    Performs mathematical calculations.
    """


    try:

        result = eval(
            expression,
            {
                "__builtins__":{}
            }
        )


        return str(result)


    except Exception as e:


        return (
            f"Calculation error: {str(e)}"
        )