import openai
import os

def get_openai_recommendations(prompt, api_key=None):
    api_key = api_key or os.getenv('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')
    if not api_key:
        raise ValueError('OpenAI API key not set.')
    openai.api_key = api_key
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "You are a helpful assistant for EV slot booking recommendations."},
                  {"role": "user", "content": prompt}],
        max_tokens=300
    )
    return response.choices[0].message['content']
