// Optional local clipboard enhancement. Navigation and docs work without JS.
document.addEventListener("click", async event => {
  const button = event.target.closest("button[data-copy]");
  if (!button) return;
  const status = button.parentElement.querySelector("[role=status]");
  try {
    await navigator.clipboard.writeText(button.dataset.copy);
    status.textContent = "Address copied. Verify the network and receiving address before sending.";
  } catch {
    status.textContent = "Copy is unavailable here. Select and copy the full address above.";
  }
});
