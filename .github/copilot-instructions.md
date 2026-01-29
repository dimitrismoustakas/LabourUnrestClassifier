# Coding Instructions

## Core Principles

1. **Keep it simple** - Write straightforward code, avoid over-engineering
2. **No unnecessary abstractions** - Don't create custom exceptions, wrappers, or helpers unless there's clear value
3. **Minimal error handling** - Focus on the happy path, let exceptions bubble up naturally
4. **No defensive coding** - Don't add try-except blocks, default values, or fallback logic unless explicitly requested or there's clear business logic
5. **DRY when obvious** - Eliminate repetition with simple helper functions, but don't create complex abstractions
6. **No wrapper functions** - Don't create functions that just call another function; inline the logic or consolidate properly

## What NOT to do

- Don't create custom exception classes (use standard Python exceptions)
- Don't wrap everything in try-except blocks
- Don't add default behaviors or assumptions about business logic
- Don't create extensive documentation files without being asked or MD files that explain every change you make
- Don't add validation that wasn't requested
- Don't make "safe" choices "just in case"
- Don't create wrapper functions that simply call another function with error handling around it
- Don't add defensive file existence checks before operations (let the underlying library handle it)
- Don't over-abstract validation logic - a small helper is fine if it eliminates real redundancy

## What TO do

- Use standard Python exceptions
- Keep functions focused and simple
- Create helper functions when they eliminate significant code repetition
- Use type hints
- Write code that handles the expected use case well
- Add practical input sanitization (like `.strip()`) to handle real-world messy data
- Use try-except only when there's explicit business logic for handling errors
- Consolidate duplicate logic - if two functions do similar things, combine them rather than wrapping one with another
- Simplify conditionals - combine redundant checks into single expressions
- Prefer code that fails loudly over code that silently handles unexpected states

## Style

- Clean, readable code
- Helper functions to reduce repetition are encouraged when they provide clear value
- Keep validation explicit and straightforward
- Comments only when the purpose is not obvious from the code itself
- Breaking everything into tiny functions is not desirable unless it offers clear benefits or there is a business logic in breaking apart the helper functions; balance readability with simplicity
- One-liners are fine when they're readable
