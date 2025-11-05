document.addEventListener('DOMContentLoaded', function(){
    // simple tab/category filtering (front-end)
    document.querySelectorAll('.tab').forEach(function(btn){
        btn.addEventListener('click', function(){
            var cat = this.dataset.cat
            // naive: append ?category= to the current URL
            var url = new URL(window.location.href)
            url.searchParams.set('category', cat)
            window.location.href = url.toString()
        })
    })

    // Autocomplete functionality
    var searchInput = document.getElementById('search-input')
    var suggestionsBox = document.getElementById('autocomplete-suggestions')
    var searchForm = document.getElementById('search-form')
    var debounceTimer
    var currentFocus = -1

    if(searchInput && suggestionsBox){
        // Input event for autocomplete
        searchInput.addEventListener('input', function(){
            var query = this.value.trim()
            
            clearTimeout(debounceTimer)
            
            if(query.length < 1){
                hideSuggestions()
                return
            }
            
            // Debounce API call
            debounceTimer = setTimeout(function(){
                fetchSuggestions(query)
            }, 300)
        })

        // Keyboard navigation
        searchInput.addEventListener('keydown', function(e){
            var items = suggestionsBox.getElementsByClassName('autocomplete-item')
            
            if(e.key === 'ArrowDown'){
                e.preventDefault()
                currentFocus++
                addActive(items)
            } else if(e.key === 'ArrowUp'){
                e.preventDefault()
                currentFocus--
                addActive(items)
            } else if(e.key === 'Enter'){
                if(currentFocus > -1 && items[currentFocus]){
                    e.preventDefault()
                    items[currentFocus].click()
                }
            } else if(e.key === 'Escape'){
                hideSuggestions()
            }
        })

        // Click outside to close
        document.addEventListener('click', function(e){
            if(!searchForm.contains(e.target)){
                hideSuggestions()
            }
        })
    }

    function fetchSuggestions(query){
        fetch('/items/search-autocomplete/?q=' + encodeURIComponent(query))
            .then(function(response){ return response.json() })
            .then(function(data){
                displaySuggestions(data.suggestions)
            })
            .catch(function(error){
                console.error('Autocomplete error:', error)
            })
    }

    function displaySuggestions(suggestions){
        suggestionsBox.innerHTML = ''
        currentFocus = -1
        
        if(!suggestions || suggestions.length === 0){
            hideSuggestions()
            return
        }
        
        suggestions.forEach(function(suggestion){
            var item = document.createElement('div')
            item.className = 'autocomplete-item'
            
            var text = document.createElement('span')
            text.className = 'autocomplete-item-text'
            text.textContent = suggestion.text
            
            var type = document.createElement('span')
            type.className = 'autocomplete-item-type'
            type.textContent = suggestion.type
            
            item.appendChild(text)
            item.appendChild(type)
            
            item.addEventListener('click', function(){
                searchInput.value = suggestion.text
                hideSuggestions()
                searchForm.submit()
            })
            
            suggestionsBox.appendChild(item)
        })
        
        suggestionsBox.classList.add('show')
    }

    function hideSuggestions(){
        suggestionsBox.classList.remove('show')
        suggestionsBox.innerHTML = ''
        currentFocus = -1
    }

    function addActive(items){
        if(!items) return false
        removeActive(items)
        
        if(currentFocus >= items.length) currentFocus = 0
        if(currentFocus < 0) currentFocus = items.length - 1
        
        if(items[currentFocus]){
            items[currentFocus].classList.add('active')
        }
    }

    function removeActive(items){
        for(var i = 0; i < items.length; i++){
            items[i].classList.remove('active')
        }
    }

    // search form submit on enter
    if(searchForm){
        searchForm.addEventListener('submit', function(e){
            // default behavior is fine (GET)
            hideSuggestions()
        })
    }

    // site logo is now a normal link to home (no JS required)
})
