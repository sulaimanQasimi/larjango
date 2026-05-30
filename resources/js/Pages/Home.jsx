export default function Home({ framework, message }) {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">{framework}</p>
        <h1>Laravel rhythm, Django engine.</h1>
        <p>{message}</p>
        <div className="commands" aria-label="Starter commands">
          <code>./artisan make:controller PostController</code>
          <code>./artisan inertia:page Posts/Index</code>
          <code>./artisan route:list</code>
        </div>
      </section>
    </main>
  )
}
