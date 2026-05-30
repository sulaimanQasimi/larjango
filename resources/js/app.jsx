import { createInertiaApp } from '@inertiajs/react'
import { createRoot } from 'react-dom/client'

const pages = import.meta.glob('./Pages/**/*.jsx', { eager: true })

function resolvePage(name) {
  const page = pages[`./Pages/${name}.jsx`]

  if (!page) {
    return function MissingPage() {
      return (
        <main className="page">
          <h1>{name}</h1>
          <p>No page component exists at <code>resources/js/Pages/{name}.jsx</code>.</p>
        </main>
      )
    }
  }

  return page.default
}

createInertiaApp({
  page: JSON.parse(document.getElementById('app').dataset.page),
  resolve: resolvePage,
  setup({ el, App, props }) {
    createRoot(el).render(<App {...props} />)
  },
})
