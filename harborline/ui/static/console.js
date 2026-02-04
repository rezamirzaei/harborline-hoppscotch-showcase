(function () {
  const graphqlSection = document.querySelector("[data-graphql]");
  if (graphqlSection) {
    const queryInput = document.getElementById("graphql-query");
    const variablesInput = document.getElementById("graphql-variables");
    const runButton = document.getElementById("graphql-run");
    const clearButton = document.getElementById("graphql-clear");
    const output = document.getElementById("graphql-output");

    const runQuery = async () => {
      output.textContent = "Running...";
      let variables = {};
      try {
        variables = variablesInput.value ? JSON.parse(variablesInput.value) : {};
      } catch (err) {
        output.textContent = "Variables JSON is invalid.";
        return;
      }
      try {
        const response = await fetch("/graphql", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: queryInput.value, variables }),
        });
        const data = await response.json();
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        output.textContent = "GraphQL request failed.";
      }
    };

    runButton?.addEventListener("click", runQuery);
    clearButton?.addEventListener("click", () => {
      output.textContent = "";
    });
  }

  const sseSection = document.querySelector("[data-sse]");
  if (sseSection) {
    const startButton = document.getElementById("sse-start");
    const stopButton = document.getElementById("sse-stop");
    const clearButton = document.getElementById("sse-clear");
    const log = document.getElementById("sse-log");
    const orderInput = document.getElementById("sse-order-id");
    let source = null;

    const append = (message) => {
      log.textContent = `${message}\n${log.textContent}`;
    };

    startButton?.addEventListener("click", () => {
      if (source) {
        source.close();
      }
      const orderId = orderInput?.value?.trim();
      const url = orderId ? `/stream/orders?order_id=${encodeURIComponent(orderId)}` : "/stream/orders";
      source = new EventSource(url);
      source.onmessage = (event) => append(event.data);
      source.addEventListener("error", () => append("SSE error or disconnected"));
    });

    stopButton?.addEventListener("click", () => {
      if (source) {
        source.close();
        source = null;
        append("SSE stopped");
      }
    });

    clearButton?.addEventListener("click", () => {
      log.textContent = "";
    });
  }

  const wsSection = document.querySelector("[data-ws]");
  if (wsSection) {
    const connectButton = document.getElementById("ws-connect");
    const disconnectButton = document.getElementById("ws-disconnect");
    const clearButton = document.getElementById("ws-clear");
    const log = document.getElementById("ws-log");
    let socket = null;

    const append = (message) => {
      log.textContent = `${message}\n${log.textContent}`;
    };

    connectButton?.addEventListener("click", () => {
      if (socket) {
        socket.close();
      }
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${protocol}://${window.location.host}/ws/shipments`);
      socket.onopen = () => append("WS connected");
      socket.onmessage = (event) => append(event.data);
      socket.onerror = () => append("WS error");
      socket.onclose = () => append("WS closed");
    });

    disconnectButton?.addEventListener("click", () => {
      if (socket) {
        socket.close();
        socket = null;
      }
    });

    clearButton?.addEventListener("click", () => {
      log.textContent = "";
    });
  }
})();
