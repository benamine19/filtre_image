/**
 * Script pour gérer les notifications toast
 */

// Afficher le toast au chargement de la page
document.addEventListener('DOMContentLoaded', function() {
    // Trouver tous les toasts
    var toastElList = document.querySelectorAll('.toast');
    
    if (toastElList.length > 0) {
        // Initialiser les toasts Bootstrap
        var toastList = Array.from(toastElList).map(function(toastEl) {
            var toast = new bootstrap.Toast(toastEl, {
                animation: true,
                autohide: true,
                delay: 5000 // Disparaît après 5 secondes
            });
            
            // Afficher le toast
            toast.show();
            return toast;
        });
    }
});
