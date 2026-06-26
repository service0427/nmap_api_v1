// Human readable byte formatter
export function formatBytes(bytes, decimals = 2) {
  if (!bytes || bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

export function copyToClipboard(text, btnElement) {
  if (!navigator.clipboard) {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand("copy");
      if (btnElement) {
        const origText = btnElement.innerText;
        btnElement.innerText = "복사됨";
        btnElement.style.background = "var(--color-success)";
        setTimeout(() => {
          btnElement.innerText = origText;
          btnElement.style.background = "";
        }, 1000);
      }
    } catch (err) {
      console.error("Fallback copy failed", err);
    }
    document.body.removeChild(textarea);
    return;
  }
  navigator.clipboard.writeText(text).then(() => {
    if (btnElement) {
      const origText = btnElement.innerText;
      btnElement.innerText = "복사됨";
      btnElement.style.background = "var(--color-success)";
      setTimeout(() => {
        btnElement.innerText = origText;
        btnElement.style.background = "";
      }, 1000);
    }
  }).catch(err => {
    console.error("Clipboard copy failed", err);
  });
}

window.copyToClipboard = copyToClipboard;
