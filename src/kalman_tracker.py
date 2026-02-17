#!/usr/bin/env python3
"""
Kalman Filter Tracker Module
=============================
Provides smooth trajectory tracking using Kalman filtering.

Phase 3 Implementation - Real-World Robustness for Kitchen Environment
Handles noisy detections, predictions during occlusions, and smooth velocity.
"""

import numpy as np


class KalmanTracker:
    """
    2D Kalman filter for tracking person position and velocity.

    State vector: [x, y, vx, vy]
    - x, y: Position
    - vx, vy: Velocity

    Designed for kitchen environment with background distractions.
    """

    def __init__(
        self,
        process_noise=0.1,
        measurement_noise=10.0,
        initial_position=(0, 0),
        dt=0.033,  # ~30 FPS
    ):
        """
        Initialize Kalman filter.

        Args:
            process_noise: Process noise covariance (how much we trust the model)
            measurement_noise: Measurement noise covariance (how much we trust measurements)
            initial_position: Starting (x, y) position
            dt: Time step (seconds between frames)
        """
        self.dt = dt

        # State: [x, y, vx, vy]
        self.state = np.array(
            [
                initial_position[0],
                initial_position[1],
                0.0,  # vx
                0.0,  # vy
            ],
            dtype=float,
        )

        # State covariance matrix (uncertainty in state)
        self.covariance = np.eye(4) * 1000.0  # High initial uncertainty

        # State transition matrix (constant velocity model)
        self.F = np.array(
            [
                [1, 0, dt, 0],  # x = x + vx*dt
                [0, 1, 0, dt],  # y = y + vy*dt
                [0, 0, 1, 0],  # vx = vx
                [0, 0, 0, 1],  # vy = vy
            ]
        )

        # Measurement matrix (we measure x, y only)
        self.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])

        # Process noise covariance
        self.Q = np.eye(4) * process_noise

        # Measurement noise covariance
        self.R = np.eye(2) * measurement_noise

        # Track if we've had measurements
        self.initialized = True
        self.frames_without_update = 0
        self.max_frames_without_update = 90  # 3 seconds at 30 FPS

    def predict(self):
        """
        Predict next state (used when no measurement available).

        Returns:
            Predicted (x, y) position
        """
        # Predict state: x = F * x
        self.state = self.F @ self.state

        # Predict covariance: P = F * P * F' + Q
        self.covariance = self.F @ self.covariance @ self.F.T + self.Q

        self.frames_without_update += 1

        return self.state[0], self.state[1]

    def update(self, measurement):
        """
        Update state with new measurement.

        Args:
            measurement: Tuple of (x, y) measured position

        Returns:
            Updated (x, y) position
        """
        z = np.array(measurement, dtype=float)

        # Innovation (measurement residual): y = z - H * x
        innovation = z - (self.H @ self.state)

        # Innovation covariance: S = H * P * H' + R
        S = self.H @ self.covariance @ self.H.T + self.R

        # Kalman gain: K = P * H' * S^-1
        K = self.covariance @ self.H.T @ np.linalg.inv(S)

        # Update state: x = x + K * y
        self.state = self.state + K @ innovation

        # Update covariance: P = (I - K * H) * P
        I = np.eye(4)
        self.covariance = (I - K @ self.H) @ self.covariance

        self.frames_without_update = 0

        return self.state[0], self.state[1]

    def get_position(self):
        """
        Get current position estimate.

        Returns:
            Tuple of (x, y)
        """
        return self.state[0], self.state[1]

    def get_velocity(self):
        """
        Get current velocity estimate.

        Returns:
            Tuple of (vx, vy) in pixels/second
        """
        return self.state[2], self.state[3]

    def get_speed(self):
        """
        Get current speed (magnitude of velocity).

        Returns:
            Speed in pixels/second
        """
        vx, vy = self.get_velocity()
        return np.sqrt(vx**2 + vy**2)

    def is_lost(self):
        """
        Check if tracker has lost the target (too long without updates).

        Returns:
            True if lost, False otherwise
        """
        return self.frames_without_update > self.max_frames_without_update

    def reset(self, position):
        """
        Reset tracker to new position.

        Args:
            position: Tuple of (x, y)
        """
        self.state = np.array([position[0], position[1], 0.0, 0.0], dtype=float)

        self.covariance = np.eye(4) * 1000.0
        self.frames_without_update = 0


class MultiPersonKalmanTracker:
    """
    Manages multiple Kalman trackers for multi-person tracking.

    Designed for kitchen environment where people may temporarily disappear
    behind counters or appliances.
    """

    def __init__(self, process_noise=0.1, measurement_noise=10.0, dt=0.033):
        """
        Initialize multi-person tracker.

        Args:
            process_noise: Process noise for all trackers
            measurement_noise: Measurement noise for all trackers
            dt: Time step between frames
        """
        self.trackers = {}  # {person_id: KalmanTracker}
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        self.dt = dt

    def create_tracker(self, person_id, initial_position):
        """
        Create new tracker for a person.

        Args:
            person_id: Unique person identifier
            initial_position: Starting (x, y) position
        """
        self.trackers[person_id] = KalmanTracker(
            process_noise=self.process_noise,
            measurement_noise=self.measurement_noise,
            initial_position=initial_position,
            dt=self.dt,
        )

    def update_tracker(self, person_id, measurement):
        """
        Update tracker with new measurement.

        Args:
            person_id: Person identifier
            measurement: Tuple of (x, y) position

        Returns:
            Smoothed (x, y) position
        """
        if person_id not in self.trackers:
            # Create new tracker
            self.create_tracker(person_id, measurement)
            return measurement

        return self.trackers[person_id].update(measurement)

    def predict_tracker(self, person_id):
        """
        Predict position for a tracker (when no measurement available).

        Args:
            person_id: Person identifier

        Returns:
            Predicted (x, y) position or None if tracker doesn't exist
        """
        if person_id not in self.trackers:
            return None

        return self.trackers[person_id].predict()

    def get_position(self, person_id):
        """
        Get current position for a person.

        Args:
            person_id: Person identifier

        Returns:
            (x, y) position or None
        """
        if person_id not in self.trackers:
            return None

        return self.trackers[person_id].get_position()

    def get_velocity(self, person_id):
        """
        Get velocity for a person.

        Args:
            person_id: Person identifier

        Returns:
            (vx, vy) velocity or None
        """
        if person_id not in self.trackers:
            return None

        return self.trackers[person_id].get_velocity()

    def get_speed(self, person_id):
        """
        Get speed for a person.

        Args:
            person_id: Person identifier

        Returns:
            Speed in pixels/second or None
        """
        if person_id not in self.trackers:
            return None

        return self.trackers[person_id].get_speed()

    def is_lost(self, person_id):
        """
        Check if a tracker is lost.

        Args:
            person_id: Person identifier

        Returns:
            True if lost or doesn't exist, False otherwise
        """
        if person_id not in self.trackers:
            return True

        return self.trackers[person_id].is_lost()

    def remove_tracker(self, person_id):
        """
        Remove a tracker.

        Args:
            person_id: Person identifier
        """
        if person_id in self.trackers:
            del self.trackers[person_id]

    def cleanup_lost_trackers(self):
        """
        Remove all lost trackers.

        Returns:
            List of removed person IDs
        """
        lost_ids = [pid for pid in self.trackers.keys() if self.trackers[pid].is_lost()]

        for pid in lost_ids:
            self.remove_tracker(pid)

        return lost_ids

    def get_all_positions(self):
        """
        Get positions for all tracked people.

        Returns:
            Dictionary {person_id: (x, y)}
        """
        return {pid: tracker.get_position() for pid, tracker in self.trackers.items()}

    def get_active_count(self):
        """
        Get number of active trackers.

        Returns:
            Count of active trackers
        """
        return len(self.trackers)


def smooth_trajectory(trajectory_points, window_size=5):
    """
    Apply simple moving average smoothing to trajectory.

    Useful for visualization when Kalman filter is not used.

    Args:
        trajectory_points: List of (x, y, time) tuples
        window_size: Number of points to average

    Returns:
        Smoothed list of (x, y, time) tuples
    """
    if len(trajectory_points) < window_size:
        return trajectory_points

    smoothed = []

    for i in range(len(trajectory_points)):
        # Get window of points
        start = max(0, i - window_size // 2)
        end = min(len(trajectory_points), i + window_size // 2 + 1)

        window = trajectory_points[start:end]

        # Average x and y
        avg_x = sum(p[0] for p in window) / len(window)
        avg_y = sum(p[1] for p in window) / len(window)

        # Keep original timestamp
        smoothed.append((avg_x, avg_y, trajectory_points[i][2]))

    return smoothed


def calculate_velocity_from_trajectory(trajectory_points, pixels_per_meter=100):
    """
    Calculate velocity from trajectory points.

    Args:
        trajectory_points: List of (x, y, time) tuples
        pixels_per_meter: Conversion factor

    Returns:
        Velocity in m/s or None if insufficient points
    """
    if len(trajectory_points) < 2:
        return None

    # Use last two points
    (x1, y1, t1) = trajectory_points[-2]
    (x2, y2, t2) = trajectory_points[-1]

    # Distance in pixels
    distance_pixels = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    # Time difference
    time_delta = t2 - t1

    if time_delta <= 0:
        return None

    # Convert to m/s
    distance_meters = distance_pixels / pixels_per_meter
    velocity = distance_meters / time_delta

    return velocity
