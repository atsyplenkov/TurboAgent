PORT     ?= 8888
RUN_DIR  := .turbo-agent
PID_FILE := $(RUN_DIR)/turbo-agent.pid
LOG_FILE := $(RUN_DIR)/turbo-agent.log
BIN      := $(if $(wildcard .venv/bin/turbo-agent),.venv/bin/turbo-agent,turbo-agent)

.PHONY: start stop restart status

# Start turbo-agent in the background on $(PORT), unless the tracked PID is already alive.
# Waits 1s and checks the process again to catch an immediate crash.
start:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "turbo-agent already running (pid $$(cat $(PID_FILE)), port $(PORT))"; \
	else \
		mkdir -p $(RUN_DIR); \
		nohup $(BIN) -p $(PORT) > $(LOG_FILE) 2>&1 < /dev/null & \
		echo $$! > $(PID_FILE); \
		sleep 1; \
		if kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
			echo "turbo-agent started (pid $$(cat $(PID_FILE)), port $(PORT), log $(LOG_FILE))"; \
		else \
			echo "turbo-agent failed to start, see $(LOG_FILE)"; \
			rm -f $(PID_FILE); \
			exit 1; \
		fi; \
	fi

# Stop the tracked turbo-agent with SIGTERM, force-killing it after about 5s if it does not exit.
# Removes the PID file even when nothing was running.
stop:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		pid=$$(cat $(PID_FILE)); \
		kill $$pid; \
		for i in 1 2 3 4 5 6 7 8 9 10; do \
			kill -0 $$pid 2>/dev/null || break; \
			sleep 0.5; \
		done; \
		if kill -0 $$pid 2>/dev/null; then \
			kill -9 $$pid; \
			echo "turbo-agent (pid $$pid) did not exit on SIGTERM, killed"; \
		else \
			echo "turbo-agent stopped (pid $$pid)"; \
		fi; \
	else \
		echo "turbo-agent is not running"; \
	fi; \
	rm -f $(PID_FILE)

# Stop and then start turbo-agent.
restart: stop start

# Show whether the tracked turbo-agent is running and list any process listening on $(PORT).
# Always exits 0, even when the proxy is down.
status:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "turbo-agent running (pid $$(cat $(PID_FILE)), port $(PORT), log $(LOG_FILE))"; \
	else \
		echo "turbo-agent is not running"; \
	fi; \
	if ss -ltnH 'sport = :$(PORT)' | grep -q .; then \
		echo "port $(PORT) is in use:"; \
		ss -ltnpH 'sport = :$(PORT)'; \
	fi
