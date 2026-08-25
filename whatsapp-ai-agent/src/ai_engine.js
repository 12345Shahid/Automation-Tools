const dotenv = require('dotenv');
dotenv.config();

const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
const SYSTEM_PROMPT = process.env.SYSTEM_PROMPT || "You are a helpful assistant.";

// In-memory conversation history
// Format: { '1234567890': [ {role: 'user', content: '...'}, ... ] }
const conversationMemory = new Map();
const MAX_HISTORY = 10;

async function generateResponse(userNumber, incomingText) {
    if (!OPENROUTER_API_KEY) {
        console.error('❌ OPENROUTER_API_KEY is missing!');
        return 'Sorry, my AI brain is disconnected at the moment.';
    }

    // 1. Get or initialize conversation history
    if (!conversationMemory.has(userNumber)) {
        conversationMemory.set(userNumber, []);
    }
    const history = conversationMemory.get(userNumber);

    // 2. Add new user message
    history.push({ role: 'user', content: incomingText });

    // 3. Keep history within limit
    if (history.length > MAX_HISTORY) {
        history.shift(); // Remove oldest
    }

    // 4. Construct messages payload
    const messages = [
        { role: 'system', content: SYSTEM_PROMPT },
        ...history
    ];

    try {
        console.log(`🧠 Generating response for ${userNumber}...`);
        const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/12345Shahid/calls-r', // Optional, for OpenRouter rankings
                'X-Title': 'WhatsApp AI Agent'
            },
            body: JSON.stringify({
                model: 'deepseek/deepseek-v4-pro',
                messages: messages,
                max_tokens: 1000, // DeepSeek requires more tokens for its reasoning phase
                temperature: 0.7
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`OpenRouter API Error: ${response.status} - ${errorText}`);
        }

        const data = await response.json();
        const content = data.choices[0]?.message?.content;
        
        if (!content) {
            console.error('❌ OpenRouter returned null/empty content:', JSON.stringify(data, null, 2));
            throw new Error('Received empty content from AI API.');
        }

        const aiText = content.trim();

        // 5. Save AI response to history
        history.push({ role: 'assistant', content: aiText });

        return aiText;
    } catch (error) {
        console.error('❌ Error generating AI response:', error.message);
        // Remove the user message from history if generation failed to prevent context corruption
        history.pop();
        return 'Sorry, I am having trouble processing that right now.';
    }
}

module.exports = { generateResponse, conversationMemory };
