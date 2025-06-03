## Streaming Responses
LiteLLM supports streaming the model response back by passing stream=True as an argument to the completion function
### NOTE
- in case you didn't get information you need, check link https://context7.com/berriai/litellm/llms.txt to get full context of litellm

### Usage
from litellm import completion
messages = [{"role": "user", "content": "Hey, how's it going?"}]
response = completion(model="gpt-3.5-turbo", messages=messages, stream=True)
for part in response:
    print(part.choices[0].delta.content or "")

### Helper function
LiteLLM also exposes a helper function to rebuild the complete streaming response from the list of chunks.

from litellm import completion
messages = [{"role": "user", "content": "Hey, how's it going?"}]
response = completion(model="gpt-3.5-turbo", messages=messages, stream=True)

for chunk in response: 
    chunks.append(chunk)

print(litellm.stream_chunk_builder(chunks, messages=messages))

## Async Completion
Asynchronous Completion with LiteLLM. LiteLLM provides an asynchronous version of the completion function called acompletion

### Usage
from litellm import acompletion
import asyncio

async def test_get_response():
    user_message = "Hello, how are you?"
    messages = [{"content": user_message, "role": "user"}]
    response = await acompletion(model="gpt-3.5-turbo", messages=messages)
    return response

response = asyncio.run(test_get_response())
print(response)


## Async Streaming
We've implemented an __anext__() function in the streaming object returned. This enables async iteration over the streaming object.

### Usage
Here's an example of using it with openai.

from litellm import acompletion
import asyncio, os, traceback

async def completion_call():
    try:
        print("test acompletion + streaming")
        response = await acompletion(
            model="gpt-3.5-turbo", 
            messages=[{"content": "Hello, how are you?", "role": "user"}], 
            stream=True
        )
        print(f"response: {response}")
        async for chunk in response:
            print(chunk)
    except:
        print(f"error occurred: {traceback.format_exc()}")
        pass

asyncio.run(completion_call())