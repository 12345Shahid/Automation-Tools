const { generateResponse, conversationMemory } = require('./src/ai_engine');

async function runTests() {
    console.log("🚀 Starting AI Engine Local Tests...\n");
    const testNumber = "1234567890";

    // Test 1: First interaction
    console.log("--- Test 1: First Message ---");
    const msg1 = "Hi, what services do you offer?";
    console.log(`User: ${msg1}`);
    const reply1 = await generateResponse(testNumber, msg1);
    console.log(`AI: ${reply1}\n`);

    // Test 2: Context retention (Memory)
    console.log("--- Test 2: Follow-up (Context Retention) ---");
    const msg2 = "How much for a roof inspection?";
    console.log(`User: ${msg2}`);
    const reply2 = await generateResponse(testNumber, msg2);
    console.log(`AI: ${reply2}\n`);
    
    // Check Memory Array
    const history = conversationMemory.get(testNumber);
    console.log("--- Memory State ---");
    console.log(`Total messages in history: ${history.length} (Expected 4)`);
    if (history.length === 4) {
        console.log("✅ Context memory is working perfectly.");
    } else {
        console.log("❌ Memory state is incorrect.");
    }
}

runTests().catch(err => {
    console.error("❌ Test failed:", err);
    process.exit(1);
});
