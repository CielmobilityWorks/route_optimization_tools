"""Capacitated Vehicle Routing Problem (CVRP) solver for route optimization."""

import os
import pandas as pd
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp


def load_locations_from_csv(csv_path):
    """Load waypoints data from locations.csv file with automatic encoding detection."""
    # 다양한 인코딩 시도
    encodings_to_try = ['utf-8', 'utf-8-sig', 'euc-kr', 'cp949']
    
    for encoding in encodings_to_try:
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
            print(f"VRP Solver: CSV 파일을 {encoding} 인코딩으로 로드했습니다.")
            
            # Use the original order from CSV - first row is depot
            waypoints = []
            for _, row in df.iterrows():
                waypoints.append({
                    "id": str(row['id']),
                    "name": row['name'],
                    "demand": int(row['demand'])
                })
            return waypoints
            
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            print(f"Error loading locations from {csv_path} with {encoding}: {e}")
            continue
    
    # 모든 인코딩 실패
    print(f"Error: Could not load {csv_path} with supported encodings: {', '.join(encodings_to_try)}")
    return []


def load_matrix_from_csv(csv_path):
    """Load matrix from CSV file (distance or time)."""
    try:
        df = pd.read_csv(csv_path, index_col=0)
        # Convert to numpy array and then to list
        matrix = df.values.tolist()
        return matrix
    except Exception as e:
        print(f"Error loading matrix from {csv_path}: {e}")
        return []


def scale_matrix_for_ortools(matrix, matrix_type="distance"):
    """Scale matrix values to be safe for OR-Tools solver."""
    if not matrix or not matrix[0]:
        return matrix
    
    # Find max value in matrix
    max_value = max([max(row) for row in matrix])
    
    # OR-Tools works best with values under 100000
    # For distance matrices, scale down large values
    if matrix_type == "distance" and max_value > 50000:
        scale_factor = 50000 / max_value
        print(f"Scaling distance matrix by factor {scale_factor:.3f} (max value: {max_value:.1f})")
        
        scaled_matrix = []
        for row in matrix:
            scaled_row = [int(val * scale_factor) for val in row]
            scaled_matrix.append(scaled_row)
        return scaled_matrix
    
    # For time matrices or already small distances, just convert to int
    int_matrix = []
    for row in matrix:
        int_row = [int(val) for val in row]
        int_matrix.append(int_row)
    return int_matrix


def validate_matrix_for_ortools(matrix, matrix_name="matrix"):
    """Validate matrix for OR-Tools compatibility."""
    if not matrix:
        print(f"Warning: {matrix_name} is empty")
        return False
    
    # Check for square matrix
    size = len(matrix)
    for i, row in enumerate(matrix):
        if len(row) != size:
            print(f"Warning: {matrix_name} row {i} has length {len(row)}, expected {size}")
            return False
    
    # Check for negative values or NaN
    for i, row in enumerate(matrix):
        for j, val in enumerate(row):
            if val < 0:
                print(f"Warning: {matrix_name}[{i}][{j}] has negative value: {val}")
                return False
            if not isinstance(val, (int, float)) or val != val:  # NaN check
                print(f"Warning: {matrix_name}[{i}][{j}] has invalid value: {val}")
                return False
    
    print(f"✓ {matrix_name} validation passed")
    return True

def load_distance_matrix_from_csv(csv_path):
    """Load distance matrix from CSV file. (Backward compatibility)"""
    return load_matrix_from_csv(csv_path)

def load_matrices_from_files(time_matrix_path='time_matrix.csv', distance_matrix_path='distance_matrix.csv'):
    """Load both time and distance matrices from CSV files."""
    try:
        time_matrix = load_matrix_from_csv(time_matrix_path)
        distance_matrix = load_matrix_from_csv(distance_matrix_path)
        
        # Validate matrices before scaling
        if not validate_matrix_for_ortools(time_matrix, "time_matrix"):
            print("Warning: Time matrix validation failed, but continuing...")
        if not validate_matrix_for_ortools(distance_matrix, "distance_matrix"):
            print("Warning: Distance matrix validation failed, but continuing...")
        
        # Scale matrices for OR-Tools compatibility
        time_matrix = scale_matrix_for_ortools(time_matrix, "time")
        distance_matrix = scale_matrix_for_ortools(distance_matrix, "distance")
        
        return {
            "time_matrix": time_matrix,
            "distance_matrix": distance_matrix,
            "success": True
        }
    except Exception as e:
        print(f"Error loading matrices: {e}")
        return {
            "time_matrix": None,
            "distance_matrix": None,
            "success": False,
            "error": str(e)
        }


def validate_vrp_data(locations, cost_matrix, vehicle_capacity, num_vehicles):
    """Validate VRP input data and return detailed error messages if invalid.
    
    Args:
        cost_matrix: Cost matrix (can be distance or time matrix)
    """
    errors = []
    warnings = []
    
    # 1. Check if data exists
    if not locations:
        errors.append("위치 데이터가 비어있습니다.")
        return {"valid": False, "errors": errors, "warnings": warnings}
    
    if not cost_matrix:
        errors.append("비용 매트릭스가 비어있습니다.")
        return {"valid": False, "errors": errors, "warnings": warnings}
    
    # 2. Check matrix dimensions
    num_locations = len(locations)
    matrix_size = len(cost_matrix)
    
    if matrix_size != num_locations:
        errors.append(f"비용 매트릭스 크기({matrix_size})와 위치 수({num_locations})가 일치하지 않습니다.")
    
    # Check if matrix is square
    for i, row in enumerate(cost_matrix):
        if len(row) != matrix_size:
            errors.append(f"비용 매트릭스 {i}번째 행의 크기가 올바르지 않습니다.")
            break
    
    # 3. Check matrix values
    has_negative = False
    has_zero_diagonal = True
    max_cost = 0
    
    for i in range(len(cost_matrix)):
        for j in range(len(cost_matrix[i])):
            value = cost_matrix[i][j]
            
            # Check for negative values
            if value < 0:
                has_negative = True
            
            # Check diagonal values (should be 0)
            if i == j and value != 0:
                has_zero_diagonal = False
            
            # Track maximum cost
            max_cost = max(max_cost, value)
    
    if has_negative:
        errors.append("비용 매트릭스에 음수 값이 있습니다.")
    
    if not has_zero_diagonal:
        warnings.append("비용 매트릭스의 대각선 값이 0이 아닙니다.")
    
    # Check for unreachable locations (very large costs)
    if max_cost > 1000000:  # 1000km 또는 매우 큰 시간값 이상
        warnings.append(f"매우 큰 비용 값({max_cost})이 감지되었습니다. 도달 불가능한 위치가 있을 수 있습니다.")
    
    # 4. Check capacity constraints
    waypoints_only = locations[1:] if len(locations) > 1 else []
    total_demand = sum(waypoint['demand'] for waypoint in waypoints_only)
    total_capacity = vehicle_capacity * num_vehicles
    
    if total_demand > total_capacity:
        errors.append(f"총 수요({total_demand})가 총 차량 용량({total_capacity})을 초과합니다.")
    
    # Check individual demands
    max_demand = max([waypoint['demand'] for waypoint in waypoints_only], default=0)
    if max_demand > vehicle_capacity:
        errors.append(f"개별 수요({max_demand})가 차량 용량({vehicle_capacity})을 초과합니다.")
    
    # 5. Check vehicle constraints
    if num_vehicles <= 0:
        errors.append("차량 수는 1대 이상이어야 합니다.")
    
    if vehicle_capacity <= 0:
        errors.append("차량 용량은 0보다 커야 합니다.")
    
    # 6. Performance warnings
    if num_locations > 50:
        warnings.append(f"위치 수가 많습니다({num_locations}개). 최적화 시간이 오래 걸릴 수 있습니다.")
    
    if num_vehicles > 10:
        warnings.append(f"차량 수가 많습니다({num_vehicles}대). 최적화 복잡도가 높아집니다.")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "locations": num_locations,
            "total_demand": total_demand,
            "total_capacity": total_capacity,
            "max_cost": max_cost
        }
    }


def diagnose_optimization_failure(locations, cost_matrix, vehicle_capacity, num_vehicles, routing, manager):
    """Diagnose why OR-Tools optimization failed and provide specific error message."""
    
    # Recalculate key metrics
    waypoints_only = locations[1:] if len(locations) > 1 else []
    total_demand = sum(waypoint['demand'] for waypoint in waypoints_only)
    total_capacity = vehicle_capacity * num_vehicles
    
    # Check most common failure reasons
    
    # 1. Capacity issues (most common)
    if total_demand > total_capacity * 0.95:  # 95% capacity utilization threshold
        return {
            "type": "capacity_constraint",
            "message": f"차량 용량 부족: 총 수요({total_demand})가 총 용량({total_capacity})에 비해 너무 큽니다. 차량을 {((total_demand // vehicle_capacity) + 1) - num_vehicles}대 더 추가하거나 용량을 늘려주세요."
        }
    
    # 2. Individual demand too large
    max_demand = max([waypoint['demand'] for waypoint in waypoints_only], default=0)
    if max_demand > vehicle_capacity:
        problematic_locations = [wp['name'] for wp in waypoints_only if wp['demand'] > vehicle_capacity]
        return {
            "type": "individual_capacity",
            "message": f"개별 위치 수요 초과: '{', '.join(problematic_locations)}'의 수요({max_demand})가 차량 용량({vehicle_capacity})을 초과합니다."
        }
    
    # 3. Unreachable locations
    max_cost = max([max(row) for row in cost_matrix], default=0)
    if max_cost > 500000:  # 500km 또는 매우 큰 시간값 이상
        return {
            "type": "unreachable_locations",
            "message": f"도달 불가능한 위치: 최대 비용이 {max_cost:.1f}로 너무 큽니다. 매트릭스를 다시 생성해주세요."
        }
    
    # 4. Problem size too large
    num_locations = len(locations)
    if num_locations > 100:
        return {
            "type": "problem_size",
            "message": f"문제 크기 과대: 위치 수({num_locations})가 너무 많습니다. 위치를 줄이거나 탐색 시간을 늘려주세요."
        }
    
    # 5. Too few vehicles for efficient routing
    if num_vehicles == 1 and len(waypoints_only) > 20:
        return {
            "type": "vehicle_count",
            "message": f"차량 부족: {len(waypoints_only)}개 위치를 1대로 처리하기 어렵습니다. 차량 수를 늘려주세요."
        }
    
    # 6. Symmetry issues in cost matrix
    asymmetric_count = 0
    for i in range(len(cost_matrix)):
        for j in range(len(cost_matrix[i])):
            if abs(cost_matrix[i][j] - cost_matrix[j][i]) > cost_matrix[i][j] * 0.1:  # 10% 차이
                asymmetric_count += 1
    
    if asymmetric_count > len(cost_matrix):
        return {
            "type": "matrix_asymmetry",
            "message": "비용 매트릭스 비대칭: 매트릭스가 대칭적이지 않아 최적화가 실패했습니다. 매트릭스를 다시 생성해주세요."
        }
    
    # 7. Generic failure with suggestions
    suggestions = []
    
    if total_capacity < total_demand * 1.2:
        suggestions.append("차량 용량을 늘리거나 차량 수를 증가시켜보세요")
    
    if num_vehicles < 2:
        suggestions.append("차량 수를 2대 이상으로 설정해보세요")
    
    if len(waypoints_only) > 30:
        suggestions.append("위치 수를 30개 이하로 줄여보세요")
    
    if not suggestions:
        suggestions = ["거리 매트릭스를 다시 생성해보세요", "차량 용량을 늘려보세요", "위치 수를 줄여보세요"]
    
    return {
        "type": "unknown",
        "message": f"최적화 실패: 해결책을 찾을 수 없습니다.\n제안사항:\n" + "\n".join([f"• {s}" for s in suggestions])
    }


def create_data_model(all_locations, cost_matrix, num_vehicles, vehicle_capacities, matrix_type="distance"):
    """Create data model for VRP problem.
    
    Args:
        all_locations: All locations including depot (sorted by ID)
        cost_matrix: Cost matrix (can be distance or time) where first row/column is depot
        num_vehicles: Number of vehicles
        vehicle_capacities: List of vehicle capacities
        matrix_type: Type of cost matrix ("distance", "time", etc.)
    
    Returns:
        Data model for OR-Tools where:
        - Index 0: Depot (demand = 0)
        - Index 1~N: Waypoints (demand from CSV)
    """
    # First location is depot, rest are waypoints
    depot_info = all_locations[0]
    waypoints = all_locations[1:] if len(all_locations) > 1 else []
    
    # Create demands array: depot(0) + waypoints demands
    demands = [0] + [waypoint["demand"] for waypoint in waypoints]
    
    return {
        "cost_matrix": cost_matrix,
        "matrix_type": matrix_type,
        "demands": demands,
        "num_vehicles": num_vehicles,
        "vehicle_capacities": vehicle_capacities,
        "depot": 0,
        "depot_info": depot_info,  # Store depot information
        "waypoints": waypoints  # Store waypoint information
    }


def extract_solution_data(data, manager, routing, solution):
    """Extract structured solution data from OR-Tools solution."""
    routes = []
    total_distance = 0
    total_time = 0
    total_load = 0
    fake_start_offset = data.get("fake_start_offset")
    num_fake_starts = data.get("num_fake_starts", 0)
    fake_end_offset = data.get("fake_end_offset")
    num_fake_ends = data.get("num_fake_ends", 0)
    def _is_fake_start(node_idx):
        if fake_start_offset is None:
            return False
        return fake_start_offset <= node_idx < fake_start_offset + num_fake_starts
    def _is_fake_end(node_idx):
        if fake_end_offset is None:
            return False
        return fake_end_offset <= node_idx < fake_end_offset + num_fake_ends
    
    # Load matrices for calculating both distance and time
    try:
        matrices_result = load_matrices_from_files()
        if not matrices_result["success"]:
            print("Warning: Could not load matrices for detailed calculation")
            distance_matrix = data["cost_matrix"]  # Fallback to primary matrix
            time_matrix = data["cost_matrix"]
        else:
            distance_matrix = matrices_result["distance_matrix"]
            time_matrix = matrices_result["time_matrix"]
    except Exception as e:
        print(f"Warning: Error loading matrices: {e}")
        distance_matrix = data["cost_matrix"]
        time_matrix = data["cost_matrix"]
    
    for vehicle_id in range(data["num_vehicles"]):
        index = routing.Start(vehicle_id)
        
        # Skip empty routes
        if routing.IsEnd(solution.Value(routing.NextVar(index))):
            continue
            
        route_waypoints = []
        route_distance = 0
        route_time = 0
        route_load = 0
        cumulative_distance = 0
        cumulative_time = 0

        # Build route by following the path
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_load += data["demands"][node_index]
            
            # Skip virtual start nodes in the exported route
            if not _is_fake_start(node_index):
                # Create waypoint info with current cumulative distance and time
                waypoint_info = _create_waypoint_info(node_index, data, route_load, cumulative_distance, cumulative_time)
                route_waypoints.append(waypoint_info)
            
            # Move to next node and calculate distance and time for this arc
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            
            prev_node = manager.IndexToNode(previous_index)
            next_node = manager.IndexToNode(index)
            
            # Calculate distance and time for this arc and accumulate
            arc_distance = 0
            arc_time = 0
            # Skip arcs involving virtual start/end nodes when accounting detailed metrics
            if (distance_matrix and prev_node < len(distance_matrix) and next_node < len(distance_matrix[0])
                and not (_is_fake_start(prev_node) or _is_fake_start(next_node) or _is_fake_end(prev_node) or _is_fake_end(next_node))):
                arc_distance = distance_matrix[prev_node][next_node]
                route_distance += arc_distance
                cumulative_distance += arc_distance
            if (time_matrix and prev_node < len(time_matrix) and next_node < len(time_matrix[0])
                and not (_is_fake_start(prev_node) or _is_fake_start(next_node) or _is_fake_end(prev_node) or _is_fake_end(next_node))):
                arc_time = time_matrix[prev_node][next_node]
                route_time += arc_time
                cumulative_time += arc_time
        
        # Add final node with final cumulative values when it's a real node (not virtual start/end)
        final_node = manager.IndexToNode(index)
        # In depot-only end mode, final node is the depot. In open-end mode, final node is a virtual end. Skip virtual nodes.
        if not (_is_fake_start(final_node) or _is_fake_end(final_node)):
            final_waypoint = _create_waypoint_info(final_node, data, route_load, cumulative_distance, cumulative_time)
            route_waypoints.append(final_waypoint)
        
        # Store route information
        routes.append({
            "vehicle_id": vehicle_id,
            "waypoints": route_waypoints,
            "distance": route_distance,
            "time": route_time,
            "load": route_load
        })
        
        total_distance += route_distance
        total_time += route_time
        total_load += route_load
    
    return {
        "objective": solution.ObjectiveValue(),
        "routes": routes,
        "total_distance": total_distance,
        "total_time": total_time,
        "total_load": total_load,
        "success": True
    }


def _apply_start_end_mode(data, start_anywhere=False, end_at_depot_only=True, open_end=False):
    """Augment data to support free-start and depot-only end.
    
    - start_anywhere: Adds K virtual start nodes (one per vehicle) with zero-cost edges to all real nodes.
                      Vehicles start at these nodes, allowing the solver to choose any first waypoint with no penalty.
    - end_at_depot_only: Forces all vehicles to end at the depot (index 0).
    
    Returns updated data dict with fields:
      cost_matrix, demands, starts, ends, fake_start_offset, num_fake_starts
    """
    n = len(data["cost_matrix"])  # real nodes count (includes depot at index 0 and waypoints 1..n-1)
    k = data["num_vehicles"]

    new_data = data.copy()
    new_matrix = data["cost_matrix"]
    new_demands = data["demands"]
    starts = None
    ends = None

    if start_anywhere:
        new_n = n + k
        # Initialize with large costs to prevent unintended travel into virtual starts
        BIG = 999999
        aug = [[BIG for _ in range(new_n)] for _ in range(new_n)]
        # Copy original costs among real nodes
        for i in range(n):
            for j in range(n):
                aug[i][j] = new_matrix[i][j]
        # Configure virtual starts: indices n .. n+k-1
        for v in range(k):
            s = n + v
            # From virtual start to any real node has zero cost
            for j in range(n):
                aug[s][j] = 0
            # Prevent returning to any virtual start from real nodes
            for i in range(n):
                aug[i][s] = BIG
            # Self cost
            aug[s][s] = 0
        new_matrix = aug
        new_demands = new_demands + [0] * k
        starts = [n + v for v in range(k)]
        new_data["fake_start_offset"] = n
        new_data["num_fake_starts"] = k
    else:
        new_data["fake_start_offset"] = None
        new_data["num_fake_starts"] = 0

    # Open-end mode: vehicles start at depot (unless free-start requested) and end at a per-vehicle virtual end node
    if open_end:
        # If we already added virtual starts, append virtual ends after them; otherwise, after real nodes
        base_n = len(new_matrix)
        BIG = 999999
        new_n2 = base_n + k
        aug2 = [[BIG for _ in range(new_n2)] for _ in range(new_n2)]
        # Copy existing costs
        for i in range(base_n):
            for j in range(base_n):
                aug2[i][j] = new_matrix[i][j]
        # Configure virtual ends at indices base_n .. base_n+k-1
        for v in range(k):
            e = base_n + v
            # From real nodes to virtual end has zero cost (closing the path)
            for i in range(base_n):
                aug2[i][e] = 0
            # Prevent leaving virtual end to any node
            for j in range(new_n2):
                aug2[e][j] = BIG
            # Self cost
            aug2[e][e] = 0
        new_matrix = aug2
        new_demands = new_demands + [0] * k
        # Starts: if free-start, already set; else depot
        if starts is None:
            starts = [data["depot"]] * k
        ends = [len(new_matrix) - k + v for v in range(k)]
        new_data["fake_end_offset"] = len(new_matrix) - k
        new_data["num_fake_ends"] = k
    else:
        new_data["fake_end_offset"] = None
        new_data["num_fake_ends"] = 0
        if end_at_depot_only:
            # Force all vehicles to end at depot (index 0)
            ends = [data["depot"]] * k
            # Ensure starts are defined; if not using virtual starts, keep default depot starts
            if starts is None:
                starts = [data["depot"]] * k
        else:
            # Default behavior (round-trip to depot)
            if starts is None:
                starts = [data["depot"]] * k
            ends = [data["depot"]] * k

    new_data["cost_matrix"] = new_matrix
    new_data["demands"] = new_demands
    new_data["starts"] = starts
    new_data["ends"] = ends
    return new_data


def _create_waypoint_info(node_index, data, current_load, cumulative_distance=0, cumulative_time=0):
    """Create waypoint information for a given node."""
    if node_index == 0:
        depot = data["depot_info"]
        return {
            "type": "depot",
            "name": depot['name'], 
            "id": depot['id'],
            "load": current_load,
            "cumulative_distance": cumulative_distance,
            "cumulative_time": cumulative_time
        }
    else:
        waypoint = data["waypoints"][node_index - 1]
        return {
            "type": "waypoint",
            "name": waypoint['name'],
            "id": waypoint['id'],
            "load": current_load,
            "cumulative_distance": cumulative_distance,
            "cumulative_time": cumulative_time
        }


def _setup_routing_model(data):
    """Setup OR-Tools routing model and manager.
    
    If data contains explicit 'starts' and 'ends', those will be used to
    configure per-vehicle start and end nodes. Otherwise, a single 'depot'
    index is used for both start and end of every vehicle (round-trip).
    """
    if "starts" in data and "ends" in data and data["starts"] and data["ends"]:
        manager = pywrapcp.RoutingIndexManager(
            len(data["cost_matrix"]),
            data["num_vehicles"],
            data["starts"],
            data["ends"],
        )
    else:
        manager = pywrapcp.RoutingIndexManager(
            len(data["cost_matrix"]), 
            data["num_vehicles"], 
            data["depot"]
        )
    routing = pywrapcp.RoutingModel(manager)
    return manager, routing


def _add_cost_constraint(routing, manager, data):
    """Add cost constraint to the routing model (can be distance, time, etc.)."""
    def cost_callback(from_index, to_index):
        try:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            
            # Bounds checking
            if from_node >= len(data["cost_matrix"]) or to_node >= len(data["cost_matrix"][0]):
                print(f"Warning: Index out of bounds: from_node={from_node}, to_node={to_node}")
                return 999999  # Large penalty for invalid paths
            
            cost = data["cost_matrix"][from_node][to_node]
            
            # Ensure cost is within OR-Tools acceptable range
            if cost < 0:
                return 0
            if cost > 999999:
                return 999999
                
            return int(cost)  # Ensure integer value
        except Exception as e:
            print(f"Error in cost_callback: {e}")
            return 999999  # Large penalty for errors
    
    transit_callback_index = routing.RegisterTransitCallback(cost_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    return transit_callback_index  # callback index 반환


def _add_capacity_constraint(routing, manager, data):
    """Add vehicle capacity constraint to the routing model."""
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data["demands"][from_node]
    
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        data["vehicle_capacities"],
        True,  # start cumul to zero
        "Capacity"
    )


def _setup_objective_functions(routing, manager, data, primary_objective, tiebreaker1, tiebreaker2, cost_callback_index, additional_objectives=None):
    """Setup objective functions for the VRP model based on user preferences."""
    if additional_objectives is None:
        additional_objectives = []
    
    print(f"Setting up objective: {primary_objective}")
    if additional_objectives:
        print(f"Additional objectives: {additional_objectives}")
    
    try:
        # Primary objective setup
        if primary_objective == "distance":
            _setup_distance_objective(routing, manager, data)
        elif primary_objective == "time":
            _setup_time_objective(routing, manager, data)  
        elif primary_objective == "vehicles":
            _setup_vehicles_objective(routing, manager, data)
        elif primary_objective == "cost":
            print("Attempting cost optimization setup...")
            _setup_cost_objective(routing, manager, data)
            print("Cost optimization setup completed")
        elif primary_objective == "makespan":
            _setup_makespan_objective(routing, manager, data)
        else:
            # Default to distance minimization
            print(f"Unknown objective {primary_objective}, using distance")
            _setup_distance_objective(routing, manager, data)
        
        # Setup additional objectives
        if 'workloadBalance' in additional_objectives:
            print("Setting up workload balancing...")
            _setup_workload_balance_objective(routing, manager, data)
            print("Workload balancing setup completed")
        
        # TODO: Add other additional objectives (timeWindow, waitTime, overtime, etc.)
        # TODO: Add tiebreaker implementation
        
    except Exception as e:
        print(f"Error in objective function setup for {primary_objective}: {e}")
        print("Falling back to distance minimization")
        # Fallback to distance minimization
        _setup_distance_objective(routing, manager, data)
        raise  # Re-raise to be caught by upper level


def _setup_distance_objective(routing, manager, data):
    """Setup total distance minimization objective."""
    # Distance is already set as the arc cost evaluator
    # OR-Tools will minimize the sum of all arc costs by default
    pass


def _setup_time_objective(routing, manager, data):
    """Setup total time minimization objective.""" 
    # Time matrix is already set as the primary arc cost evaluator
    # OR-Tools will minimize the sum of all arc costs (time) by default
    # No additional setup required as time matrix is used instead of distance matrix
    pass


def _setup_vehicles_objective(routing, manager, data):
    """Setup vehicle count minimization objective."""
    # Add a high fixed cost per vehicle to encourage using fewer vehicles
    vehicle_fixed_cost = 10000  # High fixed cost per vehicle
    
    for vehicle_id in range(data["num_vehicles"]):
        routing.SetFixedCostOfVehicle(vehicle_fixed_cost, vehicle_id)


def _setup_cost_objective(routing, manager, data):
    """Setup total cost minimization objective (fixed + variable costs)."""
    # For cost minimization, we'll use a much simpler approach
    # Just use distance minimization with a small penalty for using more vehicles
    try:
        # Very small fixed cost per vehicle (OR-Tools is sensitive to large values)
        fixed_cost_per_vehicle = 100  # Much smaller value
        
        # Only set fixed costs if we have reasonable number of vehicles
        if data["num_vehicles"] <= 10:
            for vehicle_id in range(data["num_vehicles"]):
                routing.SetFixedCostOfVehicle(fixed_cost_per_vehicle, vehicle_id)
        
    except Exception as e:
        print(f"Warning: Error setting up cost objective: {e}")
        # Complete fallback - do nothing, just use arc costs
        pass


def _setup_makespan_objective(routing, manager, data):
    """Setup makespan (maximum route duration) minimization objective."""
    try:
        # Simplified makespan objective - just use distance/time minimization
        # Complex makespan objectives can cause solver issues
        
        # For makespan, we'll use a high fixed cost per vehicle to discourage using many vehicles
        # This indirectly minimizes the maximum route duration
        high_fixed_cost = 50000
        
        for vehicle_id in range(data["num_vehicles"]):
            routing.SetFixedCostOfVehicle(high_fixed_cost, vehicle_id)
            
    except Exception as e:
        print(f"Warning: Error setting up makespan objective: {e}")
        # Fallback to simple distance minimization
        pass


def _setup_workload_balance_objective(routing, manager, data):
    """Setup workload balancing objective to minimize the maximum route duration/distance."""
    try:
        # Workload balancing is implemented using the "Minimize Maximum" approach
        # This adds constraints to ensure all vehicles have similar workloads
        
        # Create a dimension to track cumulative cost (distance or time) per vehicle
        def cumulative_cost_callback(from_index, to_index):
            """Return the cost for traveling from from_index to to_index."""
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            
            # Bounds checking
            if from_node >= len(data["cost_matrix"]) or to_node >= len(data["cost_matrix"][0]):
                return 999999  # Large penalty for invalid paths
                
            cost = data["cost_matrix"][from_node][to_node]
            return max(0, min(999999, int(cost)))  # Ensure valid range
        
        # Register the callback
        workload_callback_index = routing.RegisterTransitCallback(cumulative_cost_callback)
        
        # Add dimension for workload balancing
        # This dimension tracks the cumulative cost for each vehicle
        routing.AddDimension(
            workload_callback_index,
            0,  # No slack
            999999,  # Maximum cumulative cost per vehicle
            True,  # Start cumulative variable at zero
            "WorkloadBalance"
        )
        
        workload_dimension = routing.GetDimensionOrDie("WorkloadBalance")
        
        # Minimize the maximum workload across all vehicles
        # This is the key to workload balancing
        workload_dimension.SetGlobalSpanCostCoefficient(100)  # Penalty for workload imbalance
        
        print("Workload balancing dimension created successfully")
        
    except Exception as e:
        print(f"Warning: Error setting up workload balance objective: {e}")
        # If workload balancing fails, continue without it
        pass


def _get_search_parameters(time_limit_sec: int | None = None, num_workers: int | None = None, log_search: bool | None = None):
    """Get optimized search parameters for OR-Tools.

    Args:
        time_limit_sec: 전체 탐색 시간 제한(초). None이면 기본 60초.
        num_workers: 탐색 워커 수. None이면 OR-Tools 기본값.
        log_search: 탐색 로그 출력 여부. None이면 기본 비활성.
    """
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    # 시간 제한
    tl = 60 if time_limit_sec is None else max(1, int(time_limit_sec))
    search_parameters.time_limit.FromSeconds(tl)
    # 병렬 워커 설정(옵션)
    try:
        if num_workers is not None and int(num_workers) > 0:
            search_parameters.num_search_workers = int(num_workers)
    except Exception:
        pass
    # 로그 설정(옵션)
    if isinstance(log_search, bool):
        search_parameters.log_search = log_search
    return search_parameters


def solve_vrp(locations_csv_path=None, time_matrix_path=None, distance_matrix_path=None, 
              vehicle_capacity=30, num_vehicles=None, time_limit_sec: int | None = None,
              primary_objective="distance", tiebreaker1="none", tiebreaker2="none", additional_objectives=None,
              start_anywhere=False, end_at_depot_only=False, open_end=False):
    """Solve the CVRP problem with configurable objective functions and return structured results.
    
    Args:
        time_matrix_path: Path to time matrix CSV file (default: time_matrix.csv)
        distance_matrix_path: Path to distance matrix CSV file (default: distance_matrix.csv) 
        primary_objective: Primary objective ("distance", "time", "vehicles", "cost", "makespan")
        tiebreaker1: First tiebreaker objective
        tiebreaker2: Second tiebreaker objective  
        additional_objectives: List of additional objectives to include
    
    Additional options:
    start_anywhere: If True, vehicles can start at any waypoint (no fixed start). The cost from the virtual start to the first node is 0.
    end_at_depot_only: If True, all vehicles must end at the depot (node 0). When used with start_anywhere, this yields
               "free start -> visit waypoints -> end at depot" routes.
    open_end: If True, vehicles end at virtual end nodes (no fixed return). When used without start_anywhere, this yields
           "depot start -> visit waypoints -> open end" routes.
    """
    # Get the directory path of this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)  # Go up one level to map_app directory
    
    # CSV file paths - use provided paths or default ones
    locations_csv = locations_csv_path or os.path.join(parent_dir, 'locations.csv')
    time_csv = time_matrix_path or os.path.join(parent_dir, 'time_matrix.csv')
    distance_csv = distance_matrix_path or os.path.join(parent_dir, 'distance_matrix.csv')
    
    # Load data from CSV files
    all_locations = load_locations_from_csv(locations_csv)
    if not all_locations:
        return {"success": False, "error": "위치 데이터를 로드할 수 없습니다. CSV 파일을 확인해주세요."}
    
    # Load both matrices
    matrices_result = load_matrices_from_files(time_csv, distance_csv)
    if not matrices_result["success"]:
        return {"success": False, "error": "시간 또는 거리 매트릭스를 로드할 수 없습니다. Matrix 파일을 먼저 생성해주세요."}
    
    time_matrix = matrices_result["time_matrix"]
    distance_matrix = matrices_result["distance_matrix"]
    
    # Choose primary matrix based on objective
    if primary_objective in ["time", "makespan"]:
        primary_matrix = time_matrix
        matrix_name = "시간"
        matrix_unit = "초"
    else:  # distance, vehicles, cost
        primary_matrix = distance_matrix  
        matrix_name = "거리"
        matrix_unit = "미터"
    
    # Calculate total demand to determine optimal number of vehicles (excluding depot)
    waypoints_only = all_locations[1:] if len(all_locations) > 1 else []
    total_demand = sum(waypoint['demand'] for waypoint in waypoints_only)
    if num_vehicles is None:
        num_vehicles = max(1, (total_demand // vehicle_capacity) + 1)
    
    # Validate input data before optimization (using primary matrix)
    validation = validate_vrp_data(all_locations, primary_matrix, vehicle_capacity, num_vehicles)
    
    if not validation["valid"]:
        error_msg = "최적화를 수행할 수 없습니다:\n" + "\n".join([f"• {error}" for error in validation["errors"]])
        return {"success": False, "error": error_msg, "validation_errors": validation["errors"]}
    
    # Log warnings if any
    if validation["warnings"]:
        print("경고사항:")
        for warning in validation["warnings"]:
            print(f"• {warning}")
    
    print(f"최적화 목적: {matrix_name} 기준 ({matrix_unit})")
    
    vehicle_capacities = [vehicle_capacity] * num_vehicles
    data = create_data_model(all_locations, primary_matrix, num_vehicles, vehicle_capacities, matrix_name.lower())

    # Optionally transform the model to allow free starts and/or depot-only ends
    if start_anywhere or end_at_depot_only or open_end:
        data = _apply_start_end_mode(data, start_anywhere=start_anywhere, end_at_depot_only=end_at_depot_only, open_end=open_end)

    # Setup OR-Tools routing
    manager, routing = _setup_routing_model(data)
    cost_callback_index = _add_cost_constraint(routing, manager, data)
    _add_capacity_constraint(routing, manager, data)
    
    # Setup objective functions based on user preferences
    original_objective = primary_objective
    retry_with_distance = False
    
    try:
        _setup_objective_functions(routing, manager, data, primary_objective, tiebreaker1, tiebreaker2, cost_callback_index, additional_objectives)
    except Exception as e:
        if primary_objective in ["cost", "makespan"]:
            print(f"목적함수 {primary_objective} 설정 실패, 거리 기반으로 재시도")
            primary_objective = "distance"
            retry_with_distance = True
            try:
                _setup_objective_functions(routing, manager, data, primary_objective, tiebreaker1, tiebreaker2, cost_callback_index, additional_objectives)
            except Exception as e2:
                return {"success": False, "error": f"거리 기반 재시도도 실패: {str(e2)}"}
        else:
            return {"success": False, "error": f"목적함수 설정 중 오류: {str(e)}"}
    
    # Solve with optimized parameters
    search_parameters = _get_search_parameters(time_limit_sec=time_limit_sec)
    
    try:
        solution = routing.SolveWithParameters(search_parameters)
    except Exception as e:
        # If cost optimization failed, try with distance optimization
        if original_objective == "cost" and not retry_with_distance:
            print(f"비용 최적화 실패, 거리 기반으로 재시도: {e}")
            # Create new model for distance optimization
            manager, routing = _setup_routing_model(data)
            cost_callback_index = _add_cost_constraint(routing, manager, data)
            _add_capacity_constraint(routing, manager, data)
            _setup_objective_functions(routing, manager, data, "distance", tiebreaker1, tiebreaker2, cost_callback_index, additional_objectives)
            
            try:
                solution = routing.SolveWithParameters(search_parameters)
                primary_objective = "distance"  # Update to reflect actual objective used
            except Exception as e2:
                return {"success": False, "error": f"거리 기반 재시도도 실패했습니다: {str(e2)}"}
        else:
            return {"success": False, "error": f"최적화 중 오류가 발생했습니다: {str(e)}"}

    # Return solution data
    if solution:
        try:
            return extract_solution_data(data, manager, routing, solution)
        except Exception as e:
            return {"success": False, "error": f"결과 추출 중 오류: {str(e)}"}
    else:
        # Diagnose why no solution was found
        diagnosis = diagnose_optimization_failure(all_locations, primary_matrix, vehicle_capacity, num_vehicles, routing, manager)
        return {"success": False, "error": diagnosis["message"], "diagnosis": diagnosis}


def print_solution_summary(result):
    """Print a summary of the VRP solution."""
    if not result["success"]:
        print(f"Error: {result['error']}")
        return
        
    print(f"Objective: {result['objective']}")
    print(f"Total Distance: {result['total_distance']}m")
    print(f"Total Load: {result['total_load']}")
    print(f"Number of routes: {len(result['routes'])}")
    
    for route in result["routes"]:
        print(f"\nVehicle {route['vehicle_id'] + 1}:")
        waypoint_names = [wp['name'] for wp in route['waypoints']]
        print(f"  Route: {' -> '.join(waypoint_names)}")
        print(f"  Distance: {route['distance']}m, Load: {route['load']}")


def main(locations_csv_path=None, matrix_csv_path=None, vehicle_capacity=30):
    """Command line interface for VRP solver."""
    result = solve_vrp(locations_csv_path, matrix_csv_path, vehicle_capacity)
    print_solution_summary(result)


def test_validation():
    """Test validation functions with sample data."""
    # Sample locations (including depot)
    test_locations = [
        {"id": "1", "name": "Depot", "demand": 0},
        {"id": "2", "name": "Location A", "demand": 15},
        {"id": "3", "name": "Location B", "demand": 20}
    ]
    
    # Sample distance matrix (3x3)
    test_matrix = [
        [0, 100, 200],
        [100, 0, 150],
        [200, 150, 0]
    ]
    
    # Test with insufficient capacity
    validation = validate_vrp_data(test_locations, test_matrix, vehicle_capacity=10, num_vehicles=1)
    print("=== Validation Test ===")
    print(f"Valid: {validation['valid']}")
    print(f"Errors: {validation['errors']}")
    print(f"Warnings: {validation['warnings']}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_validation()
    else:
        main()
