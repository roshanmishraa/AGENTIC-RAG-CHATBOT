import os
import httpx

from langchain_core.tools import tool



BRAVE_API_KEY = os.getenv(
    "BRAVE_SEARCH_API_KEY"
)



@tool
async def web_search_tool(
    query:str
)->str:

    """
    Search latest information from web.
    """


    url = (
        "https://api.search.brave.com/"
        "res/v1/web/search"
    )


    headers = {

        "Accept":"application/json",

        "X-Subscription-Token":
        BRAVE_API_KEY

    }


    params = {

        "q":query,

        "count":5

    }


    async with httpx.AsyncClient() as client:


        response = await client.get(
            url,
            headers=headers,
            params=params
        )


    data=response.json()



    results=[]


    for item in data.get(
        "web",
        {}
    ).get(
        "results",
        []
    ):


        results.append(

            f"""
Title:
{item.get('title')}

Description:
{item.get('description')}

URL:
{item.get('url')}
"""
        )



    return "\n\n".join(results)