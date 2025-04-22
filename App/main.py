from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import subprocess
import json
import threading
import time
import os
import re
import asyncio
from ampere_setup import setup as ampere_setup
import io
import sys
import docker
from typing import List

app = FastAPI()

# Add this constant near the top of your file
OLLAMA_CONTAINERS = ['ollama-sales', 'ollama-engineering', 'ollama-research', 'ollama-hr', 'ollama-marketing']

TOTAL_CORES = 192  # Total number of cores in the system
OLLAMA_INSTANCES = ['ollama-sales', 'ollama-engineering', 'ollama-research', 'ollama-hr', 'ollama-marketing']
CPUS_PER_INSTANCE = 38  # This can be adjusted as needed

def get_docker_client():
    return docker.DockerClient(base_url='unix:///var/run/docker.sock')

def get_container_pid(client: docker.DockerClient, container_name: str) -> int:
    try:
        container = client.containers.get(container_name)
        return container.attrs['State']['Pid']
    except docker.errors.NotFound:
        print(f"Container {container_name} not found")
        return None

def set_cpu_affinity(pid: int, cpu_list: List[int]):
    cpu_list_str = ','.join(map(str, cpu_list))
    try:
        subprocess.run(['taskset', '-pc', cpu_list_str, str(pid)], check=True)
        print(f"Set CPU affinity for PID {pid} to CPUs {cpu_list_str}")
    except subprocess.CalledProcessError as e:
        print(f"Error setting CPU affinity for PID {pid}: {e}")

@app.middleware("http")
async def log_requests(request, call_next):
    print(f"Received {request.method} request to {request.url}")
    response = await call_next(request)
    return response


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Global variables to store the latest Docker stats and thread status
ollama_containers = ['ollama-sales', 'ollama-engineering', 'ollama-research', 'ollama-hr', 'ollama-marketing']
view_containers = [
    'view-assistant-1', 'view-config-1', 'view-crawler-1', 'view-dashboard-1',
    'view-director-1', 'view-embeddings-1', 'view-embeddings-2', 'view-lcproxy-1',
    'view-lcproxy-2', 'view-lcproxy-3', 'view-lcproxy-4', 'view-lexi-1',
    'view-orchestrator-1', 'view-processor-1', 'view-processor-2', 'view-storage-1',
    'view-switchboard-1', 'view-syslogserver-1', 'view-vector-1'
]
containers = ollama_containers + view_containers
latest_stats = {container: {} for container in containers}
threads = {container: None for container in containers}
stop_flags = {container: threading.Event() for container in containers}

# Use the Docker socket path
DOCKER_SOCKET = '/var/run/docker.sock'


def clean_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def run_docker_stats(container):
    cmd = ['docker', '-H', f'unix://{DOCKER_SOCKET}', 'stats', '--format', '{{json .}}', container, '--no-trunc', '--no-stream']
    try:
        while not stop_flags[container].is_set():
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            output, error = process.communicate()

            if output:
                try:
                    cleaned_output = clean_ansi(output.strip())
                    stats = json.loads(cleaned_output)
                    latest_stats[container] = stats
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON for {container}: {e}")
                    print(f"Cleaned output: {cleaned_output}")

            time.sleep(1)  # Small delay before next stats collection

    except FileNotFoundError:
        print("Docker CLI not found. Make sure it's installed and in the PATH.")
    except Exception as e:
        print(f"Error running Docker stats for {container}: {str(e)}")


@app.get("/v1.0/")
async def root():
    return {"message": "Welcome to the Ampere Demo API"}


@app.get("/v1.0/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.get("/v1.0/docker-stats/{container}")
async def get_docker_stats(container: str):
    if container not in containers:
        return {"error": "Invalid container name"}
    stats = latest_stats[container]
    return {
        "container": stats.get("Name", ""),
        "cpu_usage": stats.get("CPUPerc", ""),
        "memory_usage": stats.get("MemUsage", ""),
        "network_io": stats.get("NetIO", ""),
        "block_io": stats.get("BlockIO", ""),
        "pids": stats.get("PIDs", "")
    }


@app.get("/v1.0/start-stats/{container}")
async def start_stats(container: str):
    if container not in containers:
        return {"error": "Invalid container name"}
    if threads[container] and threads[container].is_alive():
        return {"message": f"Stats collection for {container} is already running"}

    stop_flags[container].clear()
    threads[container] = threading.Thread(target=run_docker_stats, args=(container,), daemon=True)
    threads[container].start()
    return {"message": f"Started stats collection for {container}"}


@app.get("/v1.0/stop-stats/{container}")
async def stop_stats(container: str):
    if container not in containers:
        return {"error": "Invalid container name"}
    if not threads[container] or not threads[container].is_alive():
        return {"message": f"Stats collection for {container} is not running"}

    stop_flags[container].set()
    threads[container].join(timeout=5)  # Wait for the thread to finish
    threads[container] = None
    return {"message": f"Stopped stats collection for {container}"}


@app.get("/v1.0/stats-status")
async def get_stats_status():
    return {container: threads[container] is not None and threads[container].is_alive() for container in containers}


@app.get("/v1.0/start-all-stats")
async def start_all_stats():
    messages = []
    for container in containers:
        if not threads[container] or not threads[container].is_alive():
            stop_flags[container].clear()
            threads[container] = threading.Thread(target=run_docker_stats, args=(container,), daemon=True)
            threads[container].start()
            messages.append(f"Started stats collection for {container}")
        else:
            messages.append(f"Stats collection for {container} was already running")
    return {"messages": messages}


@app.get("/v1.0/stop-all-stats")
async def stop_all_stats():
    messages = []
    for container in containers:
        if threads[container] and threads[container].is_alive():
            stop_flags[container].set()
            threads[container].join(timeout=5)  # Wait for the thread to finish
            threads[container] = None
            messages.append(f"Stopped stats collection for {container}")
        else:
            messages.append(f"Stats collection for {container} was not running")
    return {"messages": messages}


@app.get("/v1.0/all-docker-stats")
async def get_all_docker_stats():
    all_stats = {}
    view_total_cpu_usage = 0.0
    view_total_memory_usage = 0
    view_total_memory_limit = 0

    def process_container_stats(container, container_type):
        nonlocal view_total_cpu_usage, view_total_memory_usage, view_total_memory_limit
        stats = latest_stats[container]
        cpu_usage = float(stats.get("CPUPerc", "0%").rstrip('%'))
        normalized_cpu = normalize_cpu_usage(cpu_usage)
        mem_usage_str = stats.get("MemUsage", "0 / 0").split('/')
        memory_usage = parse_memory(mem_usage_str[0].strip())
        memory_limit = parse_memory(mem_usage_str[1].strip())
        memory_percentage = float(stats.get("MemPerc", "0%").rstrip('%'))

        if container_type == 'view':
            view_total_cpu_usage += cpu_usage
            view_total_memory_usage += memory_usage
            view_total_memory_limit += memory_limit

        return {
            "container": stats.get("Name", ""),
            "cpu_usage": f"{cpu_usage:.2f}%",
            "normalized_cpu_usage": f"{normalized_cpu:.2f}%",
            "memory_usage": f"{memory_usage:.2f}MiB / {memory_limit:.2f}MiB",
            "memory_percentage": f"{memory_percentage:.2f}%",
            "network_io": stats.get("NetIO", ""),
            "block_io": stats.get("BlockIO", ""),
            "pids": stats.get("PIDs", "")
        }

    # Process Ollama containers
    for container in ollama_containers:
        all_stats[container] = process_container_stats(container, 'ollama')

    # Process View containers
    for container in view_containers:
        all_stats[container] = process_container_stats(container, 'view')

    # Normalize the total CPU usage for view summary
    normalized_total_cpu_usage = normalize_cpu_usage(view_total_cpu_usage)

    # Add summary of View containers
    all_stats["view_summary"] = {
        "total_cpu_usage": f"{view_total_cpu_usage:.2f}%",
        "normalized_cpu_usage": f"{normalized_total_cpu_usage:.2f}%",
        "total_memory_usage": f"{view_total_memory_usage}MiB / {view_total_memory_limit}MiB",
        "total_memory_percentage": f"{(view_total_memory_usage / view_total_memory_limit * 100):.2f}%" if view_total_memory_limit > 0 else "0%"
    }

    # Add system load, load percentage, and memory usage to the output
    all_stats["system_load"] = get_system_load()
    all_stats["system_load_percentage"] = calculate_load_percentage()
    all_stats["system_memory_usage"] = get_memory_usage_percentage()

    return all_stats


def get_system_load():
    try:
        with open('/host/proc/loadavg', 'r') as f:
            load = f.read().strip().split()
            return {
                "1min": load[0],
                "5min": load[1],
                "15min": load[2]
            }
    except Exception as e:
        print(f"Error reading system load: {str(e)}")
        return {"error": "Unable to read system load"}


def calculate_load_percentage():
    try:
        with open('/host/proc/loadavg', 'r') as f:
            load = f.read().strip().split()
            one_min_load = float(load[0])
            five_min_load = float(load[1])
            fifteen_min_load = float(load[2])

            return {
                "1min": min(round((one_min_load / TOTAL_CORES) * 100, 2), 100),
                "5min": min(round((five_min_load / TOTAL_CORES) * 100, 2), 100),
                "15min": min(round((fifteen_min_load / TOTAL_CORES) * 100, 2), 100)
            }
    except Exception as e:
        print(f"Error calculating load percentage: {str(e)}")
        return {"error": "Unable to calculate load percentage"}


@app.get("/v1.0/system-load")
async def get_system_load_api():
    return get_system_load()


@app.get("/v1.0/system-load-percentage")
async def get_system_load_percentage():
    return calculate_load_percentage()


def get_memory_usage_percentage():
    try:
        with open('/host/proc/meminfo', 'r') as f:
            mem_info = {}
            for line in f:
                key, value = line.split(':')
                mem_info[key.strip()] = int(value.split()[0])  # Convert to KB

        total_memory = mem_info['MemTotal']
        available_memory = mem_info['MemAvailable']
        used_memory = total_memory - available_memory

        usage_percentage = (used_memory / total_memory) * 100

        return {
            "total_memory_kb": total_memory,
            "used_memory_kb": used_memory,
            "available_memory_kb": available_memory,
            "usage_percentage": round(usage_percentage, 2)
        }
    except Exception as e:
        print(f"Error calculating memory usage: {str(e)}")
        return {"error": "Unable to calculate memory usage"}


@app.get("/v1.0/system-memory-usage")
async def get_system_memory_usage():
    return get_memory_usage_percentage()


@app.get("/v1.0/run-ampere-setup")
async def run_ampere_setup():
    try:
        # Run the setup function and capture its return value
        setup_results = await asyncio.to_thread(ampere_setup)

        # Check if setup_results is a dictionary (JSON-serializable)
        if isinstance(setup_results, dict):
            return JSONResponse(content={"setup_results": setup_results})
        else:
            return JSONResponse(content={"error": "Unexpected result format from setup function"}, status_code=500)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/v1.0/set-ollama-cpu-affinity")
async def set_ollama_cpu_affinity(
    cpus_per_instance: int = Query(default=CPUS_PER_INSTANCE, description="Number of CPUs per Ollama instance"),
    start_cpu: int = Query(default=0, description="Starting CPU number")
):
    client = get_docker_client()
    
    # Calculate CPU mappings dynamically
    cpu_mappings = {}
    current_cpu = start_cpu
    for instance in OLLAMA_INSTANCES:
        end_cpu = current_cpu + cpus_per_instance
        cpu_mappings[instance] = list(range(current_cpu, end_cpu))
        current_cpu = end_cpu

    results = {}
    for container_name, cpu_list in cpu_mappings.items():
        pid = get_container_pid(client, container_name)
        if pid:
            set_cpu_affinity(pid, cpu_list)
            results[container_name] = f"Set CPU affinity to CPUs {','.join(map(str, cpu_list))}"
        else:
            results[container_name] = "Container not found"

    return JSONResponse(content={
        "results": results,
        "cpus_per_instance": cpus_per_instance,
        "start_cpu": start_cpu
    })

@app.get("/v1.0/container-info")
async def get_api_container_info():
    return get_container_info()

def get_container_info():
    # Get the hostname (container ID)
    hostname = os.environ.get('HOSTNAME', 'Unknown')

    # Initialize Docker client
    client = docker.from_env()

    try:
        # Get container information
        container = client.containers.get(hostname)
        
        # Get container name
        container_name = container.name

        # Get image name and tag
        image_name = container.image.tags[0] if container.image.tags else 'Unknown'
        
        return {
            "container_id": hostname,
            "container_name": container_name,
            "image": image_name
        }
    except docker.errors.NotFound:
        return {
            "container_id": hostname,
            "container_name": "Unknown",
            "image": "Unknown"
        }
    except Exception as e:
        return {
            "error": str(e)
        }

def normalize_cpu_usage(cpu_usage):
    # cpu_usage is already a percentage, so we don't need to multiply by 100
    return cpu_usage / TOTAL_CORES


def parse_memory(memory_string):
    # Remove any non-digit characters except for the last two (unit)
    value = ''.join(c for c in memory_string if c.isdigit() or c == '.')
    unit = memory_string[-2:].lower()

    value = float(value)
    if unit == 'kb':
        return value / 1024
    elif unit == 'mb':
        return value
    elif unit == 'gb':
        return value * 1024
    elif unit == 'tb':
        return value * 1024 * 1024
    else:
        return value  # Assume MiB if no unit is recognized


if __name__ == "__main__":
    import uvicorn

    # Start stats collection for all containers
    for container in containers:
        stop_flags[container].clear()
        threads[container] = threading.Thread(target=run_docker_stats, args=(container,), daemon=True)
        threads[container].start()

    uvicorn.run(app, host="0.0.0.0", port=8000)