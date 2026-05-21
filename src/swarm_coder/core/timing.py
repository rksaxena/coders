import time
from contextlib import contextmanager
from functools import wraps
from typing import List, Dict, Optional

class ExecutionProfiler:
    """
    A utility class to track execution times of various steps and generate a summary report.
    """
    def __init__(self):
        self.records: List[Dict[str, float]] = []

    @contextmanager
    def track_step(self, step_name: str):
        """Context manager to track the duration of a specific block of code."""
        start_time = time.time()
        try:
            yield
        finally:
            end_time = time.time()
            duration = end_time - start_time
            self.records.append({"step": step_name, "duration": duration})

    def track_function(self, step_name: Optional[str] = None):
        """Decorator to track the execution time of a function."""
        def decorator(func):
            name = step_name or func.__name__
            @wraps(func)
            def wrapper(*args, **kwargs):
                with self.track_step(name):
                    return func(*args, **kwargs)
            return wrapper
        return decorator

    def generate_report(self) -> str:
        """Generates a formatted text report of all tracked steps and their durations."""
        if not self.records:
            return "No execution steps were tracked."
            
        report = ["\n" + "="*55]
        report.append(f"{'EXECUTION TIME REPORT':^55}")
        report.append("="*55)
        
        total_time = 0.0
        for record in self.records:
            report.append(f" {record['step']:<40} | {record['duration']:8.4f} s")
            total_time += record['duration']
            
        report.append("-" * 55)
        report.append(f" {'Total Tracked Time':<40} | {total_time:8.4f} s")
        report.append("="*55 + "\n")
        
        return "\n".join(report)

# Global instance for easy importing across different modules
profiler = ExecutionProfiler()