/**
 * Dashboard Auto-Refresh and Real-Time Infrastructure Monitoring
 */
document.addEventListener("DOMContentLoaded", () => {
  // Periodically refresh system health metrics every 30 seconds
  const refreshInterval = 30000;

  async function checkSystemHealth() {
    try {
      const response = await fetch("/api/status");
      if (!response.ok) return;
      const data = await response.json();
      console.log("System health update:", data);
    } catch (e) {
      console.debug("Dashboard polling idle:", e);
    }
  }

  setInterval(checkSystemHealth, refreshInterval);
});
