/*

call this function with the following parameters:
- api_url: the URL of the API endpoint
- output_stream: the stream to which the output should be sent
- stats_stream: the stream to which the stats should be sent
- stats_buffer: a buffer to accumulate stats data
- category: the category for which stats are being received

Your task is to implement the parser and process the stats data accordingly.

Example of the API response format, note there is always a "message" then either some JSON OR a [END_OF_TEXT_STREAM] message. The END_OF_TEXT_STREAM message indicates the end of the text stream, but we still
want the message after it to get stats, source docs etc. The empty message is an indication of the end of the response stream.

this has proven to be tricky, the [END_OF_TEXT_STREAM] message is not a JSON message, so you need to handle it separately.

message	{"token": "."}
message	{"token": ""}
message	[END_OF_TEXT_STREAM]
message	{"SourceDocuments": [{"Content": "Customer Applications", "Source": "http://172.20.0.1/docs/marketing/Ampere_Optimized_PyTorch_Documentation_v1_8_0_e61744b94b.pdf", "Similarity": 0.2581167297994117, "Reranked": false}, {"Content": "Customer Applications", "Source": "http://172.20.0.1/docs/marketing/Ampere_Optimized_PyTorch_Documentation_v1_8_0_e61744b94b.pdf", "Similarity": 0.2581167297994117, "Reranked": false}, {"Content": "DESCRIPTION", "Source": "http://172.20.0.1/docs/marketing/Altra_Max_Rev_A1_DS_v1_25_20240130_73cfcc518a_4705c00046.pdf", "Similarity": 0.2531371490102158, "Reranked": false}, {"Content": "DESCRIPTION", "Source": "http://172.20.0.1/docs/marketing/Altra_Rev_A1_DS_v1_50_20240130_3375c3dec5_1c5d4604fa.pdf", "Similarity": 0.2531371490102158, "Reranked": false}, {"Content": "DESCRIPTION", "Source": "http://172.20.0.1/docs/marketing/Altra_Max_Rev_A1_DS_v1_25_20240130_73cfcc518a_4705c00046.pdf", "Similarity": 0.2531371490102158, "Reranked": false}], "LLMContext": "**Context:**\n\n**Source**\nName: http://172.20.0.1/docs/marketing/Ampere_Optimized_PyTorch_Documentation_v1_8_0_e61744b94b.pdf (Pos: 151.0, Score: 0.258)\nContent:\nCustomer Applications\n\n---\n\n**Source**\nName: http://172.20.0.1/docs/marketing/Ampere_Optimized_PyTorch_Documentation_v1_8_0_e61744b94b.pdf (Pos: 151.0, Score: 0.258)\nContent:\nCustomer Applications\n\n---\n\n**Source**\nName: http://172.20.0.1/docs/marketing/Altra_Max_Rev_A1_DS_v1_25_20240130_73cfcc518a_4705c00046.pdf (Pos: 605.0, Score: 0.253)\nContent:\nDESCRIPTION\n\n---\n\n**Source**\nName: http://172.20.0.1/docs/marketing/Altra_Rev_A1_DS_v1_50_20240130_3375c3dec5_1c5d4604fa.pdf (Pos: 610.0, Score: 0.253)\nContent:\nDESCRIPTION\n\n---\n\n**Source**\nName: http://172.20.0.1/docs/marketing/Altra_Max_Rev_A1_DS_v1_25_20240130_73cfcc518a_4705c00046.pdf (Pos: 605.0, Score: 0.253)\nContent:\nDESCRIPTION", "InferenceStats": {"TimeToFirstToken": 0.2035360336303711, "GenerationTime": 3.3092191219329834, "TokenCount": 166, "TotalTime": 3.5127551555633545, "TokensPerSecond": 50.1628915715427, "Reranked": false}}
message

 */
async function processAPIResponse(api_url, outputElementId, onStatsReceived, category, requestBody, debug = false, spinnerElement) {
    const outputElement = document.getElementById(outputElementId);
    if (!outputElement) {
        console.error(`Element with id "${outputElementId}" not found`);
        return;
    }

    try {
        if (debug) console.log(`Sending POST request to ${api_url}`);
        const response = await fetch(api_url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        if (debug) console.log('Response received, starting to read the stream');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let buffer = '';
        let isFirstContent = true;
        let isEndOfTextStream = false;
        let statsData = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                if (debug) console.log('Stream reading complete');
                break;
            }

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep the last incomplete line in the buffer

            for (const line of lines) {
                if (line.trim() === '') continue; // Skip empty lines

                if (debug) console.log('Processing line:', line);

                if (line.startsWith('data:')) {
                    const content = line.slice(5).trim(); // Remove 'data:' prefix and trim

                    if (isFirstContent) {
                        isFirstContent = false;
                        if (spinnerElement) spinnerElement.style.display = 'none';
                    }

                    if (content === '[END_OF_TEXT_STREAM]') {
                        if (debug) console.log('End of text stream reached');
                        isEndOfTextStream = true;
                    } else if (isEndOfTextStream) {
                        if (debug) console.log('Accumulating stats data:', content);
                        statsData += content;
                    } else {
                        try {
                            const jsonData = JSON.parse(content);
                            if (jsonData.token !== undefined) {
                                if (debug) console.log('Writing token:', jsonData.token);
                                outputElement.innerText += jsonData.token;
                                outputElement.scrollTop = outputElement.scrollHeight; // Autoscroll to the bottom
                            } else {
                                if (debug) console.log('Unexpected JSON data:', jsonData);
                            }
                        } catch (error) {
                            // If it's not JSON, just write the content as is
                            if (debug) console.log('Non-JSON content:', content);
                            outputElement.innerText += content;
                            outputElement.scrollTop = outputElement.scrollHeight; // Autoscroll to the bottom
                        }
                    }
                } else {
                    if (debug) console.log('Unexpected line format:', line);
                }
            }
        }

        // Process any remaining data in the buffer
        if (buffer.trim() !== '') {
            if (debug) console.log('Processing remaining buffer:', buffer);
            if (buffer.startsWith('data:')) {
                const content = buffer.slice(5).trim(); // Remove 'data:' prefix and trim
                if (isEndOfTextStream) {
                    statsData += content;
                }
            }
        }

        // Process accumulated stats data
        if (statsData) {
            if (debug) console.log('Processing accumulated stats data:', statsData);
            try {
                // Attempt to parse the stats data, handling potential incomplete JSON
                let parsedStatsData;
                if (statsData.startsWith('{') && !statsData.endsWith('}')) {
                    statsData += '}'; // Close the JSON object if it's incomplete
                }
                parsedStatsData = JSON.parse(statsData);

                if (debug) console.log('Stats data:', parsedStatsData);

                // Call the onStatsReceived callback with the parsed stats data
                if (typeof onStatsReceived === 'function') {
                    onStatsReceived({
                        category: category,
                        stats: parsedStatsData
                    });
                }
            } catch (error) {
                console.error('Error parsing stats data:', error);
            }
        }

    } catch (error) {
        console.error('Error calling API:', error);
        if (spinnerElement) spinnerElement.style.display = 'none';
    }

    if (debug) console.log('Function completed');
}