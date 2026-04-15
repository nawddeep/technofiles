export const parseLearningPathJSON = (text) => {
    if (typeof text !== 'string') return { json: null, text };
    try {
        const jsonMatch = text.trim().match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
        if (jsonMatch && jsonMatch[1]) {
            const cleanJson = jsonMatch[1].trim();
            if ((cleanJson.startsWith('{') && cleanJson.endsWith('}')) ||
                (cleanJson.startsWith('[') && cleanJson.endsWith(']'))) {
                return {
                    json: JSON.parse(cleanJson),
                    text: text.replace(jsonMatch[0], '').trim()
                };
            }
        }
    } catch {
        // Malformed JSON — fall through to plain text
    }
    return { json: null, text };
};
