<template>
    <div class="min-h-screen surface-ground">
        <!-- Simple Navbar -->
        <nav class="surface-card p-3 shadow-2 flex gap-4 align-items-center">
        <div class="text-xl font-bold text-primary mr-4">📸 SimpleGram</div>
        <router-link to="/" class="no-underline text-700 font-medium hover:text-primary">Gallery</router-link>
        <router-link to="/admin" class="no-underline text-700 font-medium hover:text-primary">Admin</router-link>
        </nav>

        <!-- Page Content -->
        <router-view />
    </div>
</template>

<style>
/* Standard resets */
body {
    margin: 0;
    font-family: var(--font-family);
}
</style>