#!/bin/bash

#!/bin/bash

# Configuration
TOTAL_CORES=192
CORES_PER_INSTANCE=32

# Container names that need CPU pinning
CONTAINERS=(
  "ollama-engineering"
  "ollama-marketing"
  "ollama-research"
  "ollama-sales"
  "ollama-hr"
)
NUM_INSTANCES=${#CONTAINERS[@]}

# Function to check if containers exist
check_containers() {
  # Check if containers exist
  echo "Checking if containers exist..."
  for container_name in "${CONTAINERS[@]}"; do
    echo "Running: docker ps -a | grep \"$container_name\""
    if ! docker ps -a | grep -q "$container_name"; then
      echo "Error: Container $container_name does not exist."
      echo "Please ensure all containers are properly created and running."
      exit 1
    fi
  done
}

# Function to calculate CPU sets for each instance
calculate_cpu_sets() {
  # Calculate starting CPU for each instance
  # We'll distribute them evenly across the available cores

  CPU_SETS=()

  for i in $(seq 0 $(($NUM_INSTANCES-1))); do
    start_cpu=$((i * CORES_PER_INSTANCE))
    end_cpu=$((start_cpu + CORES_PER_INSTANCE - 1))

    # Create the CPU set string (e.g. "0-31")
    CPU_SET="${start_cpu}-${end_cpu}"
    CPU_SETS+=("$CPU_SET")

    echo "Instance $((i+1)) will use CPU cores: $CPU_SET"
  done
}

# Function to update Docker containers with CPU pinning
update_containers() {
  for i in $(seq 0 $((NUM_INSTANCES-1))); do
    container_name="${CONTAINERS[$i]}"
    cpu_set="${CPU_SETS[$i]}"

    echo "Updating container $container_name with CPU affinity: $cpu_set"
    echo "Running: docker update --cpuset-cpus=\"$cpu_set\" \"$container_name\""

    # Update container with CPU affinity
    docker update --cpuset-cpus="$cpu_set" "$container_name"

    # Check if the update was successful
    if [ $? -eq 0 ]; then
      echo "Successfully updated $container_name"
    else
      echo "Failed to update $container_name"
    fi
  done
}

# Function to show NUMA node information
show_numa_info() {
  if command -v numactl &> /dev/null; then
    echo -e "\nNUMA Node Information:"
    echo "Running: numactl --hardware"
    numactl --hardware

    echo -e "\nRecommended NUMA considerations:"
    echo "For optimal performance, each Ollama instance should use cores from the same NUMA node if possible."
    echo "Your current configuration may span NUMA boundaries depending on your hardware."
    echo "Consider adjusting CPU assignments based on your specific NUMA topology."
  else
    echo -e "\nNUMA information not available. Install numactl for NUMA details."
    echo "You can install it with: sudo apt-get install numactl"
  fi
}

# Function to restart containers (optional)
restart_containers() {
  read -p "Do you want to restart the containers to apply changes? (y/n): " answer
  if [[ "$answer" == "y" || "$answer" == "Y" ]]; then
    # Restart containers
    for container_name in "${CONTAINERS[@]}"; do
      echo "Restarting container $container_name..."
      echo "Running: docker restart \"$container_name\""
      docker restart "$container_name"
    done

    echo "Container restart complete."
  else
    echo "Changes will take effect when containers are next restarted."
  fi
}

# Function to display container resource usage
show_resource_usage() {
  echo -e "\nCurrent container resource usage:"

  # Show containers
  for container_name in "${CONTAINERS[@]}"; do
    echo -e "\n$container_name stats:"
    echo "Running: docker stats --no-stream \"$container_name\""
    docker stats --no-stream "$container_name"
  done
}

# Main execution
echo "=== Ollama CPU Pinning Configuration ==="
echo "Total CPU cores: $TOTAL_CORES"
echo "Cores per Ollama instance: $CORES_PER_INSTANCE"
echo "Number of instances to pin: $NUM_INSTANCES"
echo "Total cores to be used for pinning: $((CORES_PER_INSTANCE * NUM_INSTANCES)) out of $TOTAL_CORES"
echo ""
echo "Configuring CPU pinning for the following containers:"
for container_name in "${CONTAINERS[@]}"; do
  echo "  - $container_name"
done

# Check if we have enough cores
if [ $((CORES_PER_INSTANCE * NUM_INSTANCES)) -gt $TOTAL_CORES ]; then
  echo "Error: Not enough CPU cores available!"
  echo "Requested: $((CORES_PER_INSTANCE * NUM_INSTANCES)) cores"
  echo "Available: $TOTAL_CORES cores"
  exit 1
fi

# Confirm before proceeding
read -p "Do you want to proceed with CPU pinning? (y/n): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Operation cancelled."
  exit 0
fi

# Execute the functions
check_containers
calculate_cpu_sets
update_containers
show_numa_info
restart_containers
show_resource_usage

echo "=== CPU pinning complete ==="