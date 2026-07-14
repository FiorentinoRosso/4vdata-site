(() => {
  const counterId = 110597182;
  const reach = (goal) => {
    if (typeof window.ym === "function") window.ym(counterId, "reachGoal", goal);
  };

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a");
    if (!link) return;
    const href = link.getAttribute("href") || "";
    if (link.dataset.goal) reach(link.dataset.goal);
    else if (href.startsWith("mailto:")) reach("contact_email");
    else if (href.includes("t.me/")) reach("contact_telegram");
    else if (href.includes("wa.me/")) reach("contact_whatsapp");
    else if (href.includes("max.ru/")) reach("contact_max");
  });
})();
