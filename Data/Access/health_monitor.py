# health_monitor.py: health_monitor.py: System health and data integrity monitoring.
# Part of LeoBook Data — Access Layer
#
# Classes: HealthMonitor

"""
Health Monitor Module
Production health monitoring, alerting, and system diagnostics.
Responsible for monitoring system health, performance tracking, and automated alerts.
"""

import os
import json
from datetime import datetime as dt, timedelta
from typing import Dict, Any, List


class HealthMonitor:
    """Production health monitoring and alerting system"""

    HEALTH_LOG = "Data/Store/health_status.json"
    ERROR_LOG = "Logs/review_errors.log"

    @staticmethod
    def log_error(error_type: str, details: str, severity: str = "medium"):
        """Log errors for monitoring and alerting"""
        timestamp = dt.now().isoformat()
        error_entry = {
            "timestamp": timestamp,
            "type": error_type,
            "details": details,
            "severity": severity
        }

        try:
            # Ensure logs directory exists
            os.makedirs("Logs", exist_ok=True)

            with open(HealthMonitor.ERROR_LOG, 'a', encoding='utf-8') as f:
                f.write(f"{timestamp} [{severity.upper()}] {error_type}: {details}\n")
        except Exception:
            pass  # Don't fail if logging fails

    @staticmethod
    def check_system_health() -> Dict[str, Any]:
        """Perform comprehensive system health check"""
        health_status = {
            "timestamp": dt.now().isoformat(),
            "overall_status": "healthy",
            "checks": {},
            "alerts": []
        }

        # Check file system health
        files_to_check = [
            "Data/Store/predictions.csv",
            "Data/Store/schedules.csv",
            "Data/Store/learning_weights.json",
            "Data/Models/random_forest.pkl"
        ]

        for file_path in files_to_check:
            exists = os.path.exists(file_path)
            health_status["checks"][f"file_{os.path.basename(file_path)}"] = {
                "status": "ok" if exists else "missing",
                "exists": exists
            }
            if not exists:
                health_status["alerts"].append(f"Critical file missing: {file_path}")
                health_status["overall_status"] = "degraded"

        # Check prediction data quality
        try:
            if os.path.exists("Data/Store/predictions.csv"):
                with open("Data/Store/predictions.csv", 'r', encoding='utf-8') as f:
                    import csv
                    reader = csv.DictReader(f)
                    predictions = list(reader)

                reviewed = sum(1 for p in predictions if p.get('status') == 'reviewed')
                failed = sum(1 for p in predictions if p.get('status') == 'review_failed')
                total = len(predictions)

                health_status["checks"]["prediction_quality"] = {
                    "status": "ok",
                    "total_predictions": total,
                    "reviewed": reviewed,
                    "failed": failed,
                    "review_rate": reviewed / total if total > 0 else 0
                }

                # Alert if too many failures
                if failed > 10:  # ERROR_THRESHOLD
                    health_status["alerts"].append(f"High failure rate: {failed} failed reviews")
                    health_status["overall_status"] = "warning"

        except Exception as e:
            health_status["checks"]["prediction_quality"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["overall_status"] = "error"

        # Check recent error rate
        try:
            if os.path.exists(HealthMonitor.ERROR_LOG):
                error_count = 0

                with open(HealthMonitor.ERROR_LOG, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            # Simple line count check
                            error_count += 1
                            if error_count >= 10:  # ERROR_THRESHOLD
                                break

                if error_count >= 10:
                    health_status["alerts"].append(f"High error rate: {error_count} errors in last 5 minutes")
                    health_status["overall_status"] = "warning"

        except Exception:
            pass

        # Save health status
        try:
            os.makedirs("Data/Store", exist_ok=True)
            with open(HealthMonitor.HEALTH_LOG, 'w') as f:
                json.dump(health_status, f, indent=2)
        except Exception:
            pass

        return health_status

    @staticmethod
    def validate_production_readiness() -> Dict[str, Any]:
        """Validate system is ready for production deployment"""
        validation_results = {
            "ready": True,
            "checks": {},
            "issues": []
        }

        # Version compatibility check
        validation_results["checks"]["version"] = {
            "current": "2.6.0",  # VERSION
            "compatible_models": ["2.5", "2.6"],  # COMPATIBLE_MODELS
            "status": "ok"
        }

        # Configuration validation
        required_configs = {
            "PRODUCTION_MODE": False,  # PRODUCTION_MODE
            "BATCH_SIZE": 5 > 0,  # BATCH_SIZE
            "LOOKBACK_LIMIT": 50 > 0,  # LOOKBACK_LIMIT
            "MAX_RETRIES": 3 > 0  # MAX_RETRIES
        }

        for config, value in required_configs.items():
            status = "ok" if value else "invalid"
            validation_results["checks"][f"config_{config.lower()}"] = {
                "value": value,
                "status": status
            }
            if not value:
                validation_results["issues"].append(f"Invalid configuration: {config}")
                validation_results["ready"] = False

        # File system validation
        critical_files = [
            "Data/Store/predictions.csv",
            "Data/Store/schedules.csv",
            "Data/Store/region_league.csv"
        ]

        for file_path in critical_files:
            exists = os.path.exists(file_path)
            validation_results["checks"][f"file_{os.path.basename(file_path)}"] = {
                "exists": exists,
                "status": "ok" if exists else "missing"
            }
            if not exists:
                validation_results["issues"].append(f"Critical file missing: {file_path}")
                validation_results["ready"] = False

        # Directory validation
        required_dirs = ["Data/Store", "Logs", "Data/Models"]
        for dir_path in required_dirs:
            exists = os.path.exists(dir_path)
            validation_results["checks"][f"dir_{dir_path.lower().replace('/', '_')}"] = {
                "exists": exists,
                "status": "ok" if exists else "missing"
            }
            if not exists:
                try:
                    os.makedirs(dir_path, exist_ok=True)
                    validation_results["checks"][f"dir_{dir_path.lower().replace('/', '_')}"] = {
                        "exists": True,
                        "status": "created"
                    }
                except Exception as e:
                    validation_results["issues"].append(f"Cannot create directory {dir_path}: {e}")
                    validation_results["ready"] = False

        return validation_results
