let isRandomizing = false;
let config;
let isRunning = false;

async function fetchConfig() {
    try {
        const response = await fetch('/config.json');
        config = await response.json();
        console.log('Config loaded:', config);
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

fetchConfig();

function setBoxData(boxNumber, data) {
    const box = document.getElementById(`box${boxNumber}`);
    if (box) {
        box.value = data;
    }
}

function setPromptData(category, data) {
    const promptArea = document.getElementById(`${category}Prompt`);
    if (promptArea) {
        promptArea.textContent = data;
    }
}

function setResponseData(category, data) {
    const responseArea = document.getElementById(`${category}Response`);
    if (responseArea) {
        responseArea.textContent = data;
    }
}

const samplePrompts = {
    sales: [
        "Describe the product's key features",
        "Explain the main benefits for customers",
        "Compare our product to competitors",
        "Outline the pricing structure",
        "Mention any current promotions"
    ],
    marketing: [
        "Describe the company culture",
        "Explain employee benefits",
        "Outline career growth opportunities",
        "Discuss work-life balance initiatives",
        "Highlight diversity and inclusion efforts"
    ],
    engineering: [
        "Explain the product's technical architecture.",
        "Discuss recent technical challenges solved",
        "Outline the development process",
        "Describe the tech stack used",
        "Highlight upcoming feature developments"
    ],
    research: [
        "Highlight a customer success story",
        "Describe community engagement initiatives",
        "Discuss user feedback implementation",
        "Explain the product's impact on users",
        "Outline community support channels"
    ],
    support: [
        "Describe the onboarding process",
        "Highlight customer support options",
        "Explain troubleshooting procedures",
        "Discuss average response times",
        "Outline self-help resources available"
    ]
};

function getRandomPrompt(category) {
    const prompts = samplePrompts[category];
    return prompts[Math.floor(Math.random() * prompts.length)];
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function updateColumn(category) {
    const chatPreset = config && config[category] ? config[category].assistant_config : null;

    if (!chatPreset) {
        console.error(`No assistant_config found for ${category}`);
        return;
    }

    while (isRandomizing) {
        const prompt = getRandomPrompt(category);
        setPromptData(category, prompt);
        await callAPI(category, prompt, chatPreset);
        await sleep(Math.random() * 5000 + 10000); // Wait between 10-15 seconds before updating the column again
    }
}

async function callAPI(category, prompt, presetGUID) {
    const apiUrl = `http://sm2:8000/v1.0/tenants/00000000-0000-0000-0000-000000000000/assistant/chat/${presetGUID}`;
    console.log(`API Call to ${presetGUID} for ${category}`);
    setResponseData(category, '');

    try {
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                messages: [{role: "user", content: prompt}]
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let responseComplete = false;
        let statsBuffer = '';

        while (true) {
            const {done, value} = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, {stream: true});
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep the last incomplete line in the buffer

            for (const line of lines) {
                const trimmedLine = line.trim();
                if (trimmedLine === '[END_OF_TEXT_STREAM]') {
                    console.log('End of text stream reached');
                    responseComplete = true;
                    continue;
                }

                if (responseComplete) {
                    // Accumulate stats data
                    statsBuffer += trimmedLine;
                    continue;
                }

                if (line.startsWith('data: ')) {
                    const content = line.slice(6).trim();
                    if (content === '[END_OF_TEXT_STREAM]') {
                        console.log('End of text stream reached');
                        responseComplete = true;
                        continue;
                    }
                    try {
                        const jsonData = JSON.parse(content);
                        if (jsonData.token) {
                            setResponseData(category, (prev) => prev + jsonData.token);
                        }
                    } catch (error) {
                        console.error('Error parsing JSON:', error);
                    }
                }
            }
        }

        // Process any remaining data in the buffer
        if (buffer.trim() !== '') {
            if (buffer.trim() === '[END_OF_TEXT_STREAM]') {
                console.log('End of text stream reached');
            } else {
                statsBuffer += buffer.trim();
            }
        }

        // Process accumulated stats data
        if (statsBuffer) {
            try {
                const statsData = JSON.parse(statsBuffer);
                console.log('Stats data received:', statsData);
                processStatsData(category, statsData);
            } catch (error) {
                console.error('Error parsing stats data:', error);
            }
        }

    } catch (error) {
        console.error('Error calling API:', error);
        setResponseData(category, 'Error: Unable to get response from API');
    }
}

function processStatsData(category, statsData) {
    // Here you can process and store the stats data
    // For example, you might want to update the UI with some of this information
    if (statsData.InferenceStats) {
        const stats = statsData.InferenceStats;
        updateStats(category, `Time: ${stats.GenerationTime.toFixed(2)}s, Tokens: ${stats.TokenCount}`);
    }

    // You might also want to store the source documents or other information for later use
    // This depends on how you want to use this data in your application
}

function updateStats(category, statsText) {
    const statsElement = document.getElementById(`${category}Stats`);
    if (statsElement) {
        statsElement.textContent = statsText;
    }
}

async function startRandomizing() {
    await fetchConfig();
    isRandomizing = true;
    const categories = ['sales', 'marketing', 'engineering', 'research', 'support'];
    categories.forEach(updateColumn);
}

function stopRandomizing() {
    isRandomizing = false;
}

document.getElementById('randomizeButton').addEventListener('click', function () {
    if (isRandomizing) {
        stopRandomizing();
        this.textContent = 'Start Randomizing';
    } else {
        startRandomizing();
        this.textContent = 'Stop Randomizing';
    }
});

document.getElementById('launchButton').insertAdjacentHTML('afterend', `
    <button id="toggleTestsButton" class="button">Start Tests</button>
`);

document.getElementById('toggleTestsButton').addEventListener('click', function() {
    if (isRunning) {
        stopAllTests();
        this.textContent = 'Start Tests';
    } else {
        runAllTests();
        this.textContent = 'Stop Tests';
    }
    isRunning = !isRunning;
});

async function runAllTests() {
    if (!config) {
        await fetchConfig();
    }

    const categories = ['sales', 'marketing', 'engineering', 'research', 'support'];
    const totalColumns = categories.length;
    const totalRows = 4;
    const initialDelayBetweenCalls = 2000; // 500ms delay between initial calls

    isRunning = true;

    async function runTestLoop(row, col) {
        const category = categories[col];

        while (isRunning) {
            const randomPrompt = samplePrompts[category][Math.floor(Math.random() * samplePrompts[category].length)];
            const outputDiv = document.getElementById(`output-${row}-${col}`);
            const promptDiv = document.querySelector(`.grid-item[data-row="${row}"][data-col="${col}"] .prompt`);

            // Animate the prompt change
            promptDiv.style.opacity = '0';
            await new Promise(resolve => setTimeout(resolve, 200));
            promptDiv.textContent = randomPrompt;
            promptDiv.title = randomPrompt; // Update the title attribute
            promptDiv.style.opacity = '1';

            // Animate the output clearing
            outputDiv.style.opacity = '0';
            await new Promise(resolve => setTimeout(resolve, 200));
            outputDiv.textContent = '';
            outputDiv.style.opacity = '1';

            await runTest(row, col, randomPrompt);

            // Small delay before starting the next test
            await new Promise(resolve => setTimeout(resolve, 500));
        }
    }

    // Start all test loops with initial delays
    for (let col = 0; col < totalColumns; col++) {
        for (let row = 0; row < totalRows; row++) {
            // Add delay for the first run of each column
            await new Promise(resolve => setTimeout(resolve, col * initialDelayBetweenCalls));
            runTestLoop(row, col);
        }
    }
}

function stopAllTests() {
    isRunning = false;
    console.log('Stopping all tests after the current round completes...');
}

function openPopup() {
    document.getElementById('promptPopup').style.display = 'block';
    renderPromptLists();
}

function closePopup() {
    document.getElementById('promptPopup').style.display = 'none';
}

function renderPromptLists() {
    const promptListsContainer = document.getElementById('promptLists');
    promptListsContainer.innerHTML = '';

    for (const [category, prompts] of Object.entries(samplePrompts)) {
        const categoryDiv = document.createElement('div');
        categoryDiv.className = 'prompt-list';
        categoryDiv.innerHTML = `
                <h3>${category.charAt(0).toUpperCase() + category.slice(1)}</h3>
                <div id="${category}Prompts"></div>
                <button onclick="addPrompt('${category}')">Add Prompt</button>
            `;
        promptListsContainer.appendChild(categoryDiv);

        const promptsContainer = document.getElementById(`${category}Prompts`);
        prompts.forEach((prompt, index) => {
            const promptDiv = document.createElement('div');
            promptDiv.className = 'prompt-item';
            promptDiv.innerHTML = `
                    <input type="text" value="${prompt}" onchange="updatePrompt('${category}', ${index}, this.value)">
                    <button onclick="deletePrompt('${category}', ${index})">Delete</button>
                `;
            promptsContainer.appendChild(promptDiv);
        });
    }
}

function addPrompt(category) {
    samplePrompts[category].push('New prompt');
    renderPromptLists();
}

function updatePrompt(category, index, newValue) {
    samplePrompts[category][index] = newValue;
}

function deletePrompt(category, index) {
    samplePrompts[category].splice(index, 1);
    renderPromptLists();
}

function savePrompts() {
    closePopup();
}

async function getContainerStats() {
    try {
        // First, get machine state to get container IDs
        const machineResponse = await fetch('http://sm2:8080/api/v1.3/machine');
        const machineInfo = await machineResponse.json();

        // Get all Docker containers info
        const containersResponse = await fetch('http://sm2:8080/api/v1.3/subcontainers/docker');
        const containersInfo = await containersResponse.json();

        const stats = [];

        // Filter and process Ollama containers
        for (const container of containersInfo) {
            // Extract container ID from the container path
            const containerId = container.name.split('/').pop();
            // Get the container name from Docker labels or aliases
            const containerName = container.aliases ? container.aliases[0] : containerId;

            if (containerName.includes('ollama')) {
                try {
                    const statResponse = await fetch(`http://sm2:8080/api/v1.3/containers/docker/${containerId}`);
                    if (!statResponse.ok) {
                        console.error(`Error fetching stats for ${containerName}: ${statResponse.status}`);
                        continue;
                    }

                    const data = await statResponse.json();

                    if (!data || !data.stats || data.stats.length < 2) {
                        continue;
                    }

                    // Get the latest stats
                    const latestStats = data.stats[data.stats.length - 1];
                    const previousStats = data.stats[data.stats.length - 2];

                    // Calculate CPU usage percentage
                    const cpuDelta = latestStats.cpu.usage.total - previousStats.cpu.usage.total;
                    const systemDelta = latestStats.cpu.system_cpu_usage - previousStats.cpu.system_cpu_usage;

                    if (systemDelta > 0) {
                        const cpuPercent = (cpuDelta / systemDelta) * latestStats.cpu.number_of_cores * 100;
                        stats.push({
                            name: containerName,
                            cpuUsage: Math.round(cpuPercent)
                        });
                    }
                } catch (error) {
                    console.error(`Error processing ${containerName}:`, error);
                }
            }
        }
        return stats;
    } catch (error) {
        console.error('Error fetching container information:', error);
        return [];
    }
}

async function updateDashboard() {
    // Update CPU and Memory usage (keeping existing random values for now)
    const cpuUsage = Math.floor(Math.random() * 100);
    document.getElementById('cpuUsage').style.width = `${cpuUsage}%`;

    const memoryUsage = Math.floor(Math.random() * 100);
    document.getElementById('memoryUsage').style.width = `${memoryUsage}%`;

    // Update Process Performance with real Ollama container data
    const processPerformance = document.getElementById('processPerformance');
    processPerformance.innerHTML = '';

    try {
        // Get stats for all Ollama containers
        const containerStats = await getContainerStats();
        console.log('Container stats:', containerStats); // Debug log

        for (const stat of containerStats) {
            const processBar = document.createElement('div');
            processBar.className = 'process-bar';
            processBar.innerHTML = `
                    <span>${stat.name}</span>
                    <div class="progress-bar">
                        <div class="progress-bar-fill" style="width: ${stat.cpuUsage}%"></div>
                    </div>
                `;
            processPerformance.appendChild(processBar);
        }
    } catch (error) {
        console.error('Error updating dashboard:', error);
    }
}

// Configuration
const layoutConfig = {
    columns: [
        {name: 'Sales', id: 'sales'},
        {name: 'Marketing', id: 'marketing'},
        {name: 'Engineering', id: 'engineering'},
        {name: 'Research', id: 'research'},
        {name: 'Support', id: 'support'}
    ],
    rowsPerColumn: 4
};

// Create the main structure
function createMainStructure() {
    const mainContainer = document.getElementById('mainContainer');
    layoutConfig.columns.forEach(column => {
        const columnDiv = document.createElement('div');
        columnDiv.className = 'column';
        columnDiv.id = `${column.id}Column`;

        // Header
        const header = document.createElement('div');
        header.className = 'column-header';
        header.id = `${column.id}Header`;
        header.textContent = column.name;
        columnDiv.appendChild(header);

        // Rows
        for (let i = 1; i <= layoutConfig.rowsPerColumn; i++) {
            const rowDiv = document.createElement('div');
            rowDiv.className = 'row';
            rowDiv.id = `${column.id}Row${i}`;

            // Input question
            const questionDiv = document.createElement('div');
            questionDiv.className = 'question';
            questionDiv.id = `${column.id}Question${i}`;
            rowDiv.appendChild(questionDiv);

            // API output
            const outputDiv = document.createElement('div');
            outputDiv.className = 'output';
            outputDiv.id = `${column.id}Output${i}`;
            rowDiv.appendChild(outputDiv);

            // Stats
            const statsDiv = document.createElement('div');
            statsDiv.className = 'stats';
            statsDiv.id = `${column.id}Stats${i}`;
            rowDiv.appendChild(statsDiv);

            columnDiv.appendChild(rowDiv);
        }

        mainContainer.appendChild(columnDiv);
    });
}

// Update content functions
function updateHeader(columnId, content) {
    document.getElementById(`${columnId}Header`).textContent = content;
}

function updateQuestion(columnId, rowNumber, content) {
    document.getElementById(`${columnId}Question${rowNumber}`).textContent = content;
}

function updateOutput(columnId, rowNumber, content) {
    document.getElementById(`${columnId}Output${rowNumber}`).textContent = content;
}

function updatePerformanceMeter(meterId, percentage) {
    const meter = document.getElementById(meterId);
    meter.style.width = `${percentage}%`;
    meter.textContent = `${percentage}%`;
}

// Initialize the page
document.addEventListener('DOMContentLoaded', () => {
    createMainStructure();

    // Example usage:
    updateHeader('sales', 'Sales Team Performance');
    updateQuestion('marketing', 2, 'What is our target audience?');
    updateOutput('engineering', 1, 'The system architecture consists of...');
    updateStats('research', 3, 'Response time: 1.2s');
    updatePerformanceMeter('cpuMeter', 65);
    updatePerformanceMeter('memoryMeter', 80);
});
