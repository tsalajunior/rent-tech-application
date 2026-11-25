if ("serviceWorker" in navigator && window.isSecureContext) {
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/service-worker.js", { scope: "/" })
            .catch((error) => {
                console.error("Impossible d'enregistrer le service worker RentTech.", error);
            });
    });
}
