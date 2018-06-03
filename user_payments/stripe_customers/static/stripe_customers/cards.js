;document.addEventListener('DOMContentLoaded', function() {
  var form = document.querySelector('form[data-publishable-key]');
  if (!form) return;

  var style = {
    base: {
      color: '#32325d',
      lineHeight: '24px',
      fontFamily: '"Helvetica Neue", Helvetica, sans-serif',
      fontSmoothing: 'antialiased',
      fontSize: '16px',
      '::placeholder': {
        color: '#aab7c4'
      }
    },
    invalid: {
      color: '#fa755a',
      iconColor: '#fa755a'
    }
  };

  var stripe = Stripe(form.getAttribute('data-publishable-key'));
  var elements = stripe.elements();
  var card = elements.create('card', {style: style, hidePostalCode: true,});
  card.mount('#card-element');
  card.addEventListener('change', function(event) {
    document.getElementById('card-errors').textContent = event.error ? event.error.message : "\u00A0";
  });

  form.addEventListener('submit', function(event) {
    event.preventDefault();
    form.querySelector('button[type="submit"]').disabled = true;

    stripe.createToken(card).then(function(result) {
      if (result.error) {
        document.getElementById('card-errors').textContent = result.error.message;
        form.querySelector('button[type="submit"]').disabled = false;
      } else {
        var input = document.createElement('input');
        input.setAttribute('type', 'hidden');
        input.setAttribute('name', 'token');
        input.setAttribute('value', result.token.id);
        form.appendChild(input);
        form.submit();
      }
    });
  });
});
