<template>
    <div class="p-4">
        <div class="surface-card p-4 shadow-1 border-round mb-4">
        <div class="grid">
            <input type="file" @change="e => file = e.target.files[0]" class="col-12 md:col-4 p-inputtext" />
            <input v-model="tag" placeholder="Tag" class="col-12 md:col-3 p-inputtext" />
            <input v-model="desc" placeholder="Desc" class="col-12 md:col-3 p-inputtext" />
            <Button label="Upload" @click="upload" icon="pi pi-plus" class="col-12 md:col-2" />
        </div>
    </div>
    
    <div class="flex mb-4">
        <span class="p-input-icon-left w-full">
            <i class="pi pi-search" />
            <InputText v-model="search" @input="load" placeholder="Filter by Tag/Description" class="w-full" />
        </span>
    </div>

    <div class="grid">
    <div v-for="img in imgs" :key="img.ImageId" class="col-12 md:col-3">
        <Card>
        <template #header><img :src="img.Url" class="w-full h-12rem border-round-top" style="object-fit: cover" /></template>
        <template #title>{{ img.Tag }}</template>
        <template #content>{{ img.Description }}</template>
        <template #footer>
            <div class="flex gap-2">
                <Button icon="pi pi-download" @click="dl(img.ImageId)" />
                <Button icon="pi pi-trash" severity="danger" @click="del(img.ImageId)" />
            </div>
        </template>
        </Card>
    </div>
    </div>
</div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import axios from 'axios';
const API = "http://localhost:8000";
const imgs = ref([]), file = ref(null), tag = ref(''), desc = ref(''), search = ref('');
const load = async () => {
    if (search.value && search.value.trim() !== '') {
        const res = await axios.get(`${API}/images/search/${encodeURIComponent(search.value.trim())}`);
        imgs.value = res.data;
    } else {
        const res = await axios.get(`${API}/images`);
        imgs.value = res.data;
    }
};
const upload = async () => {
    const fd = new FormData(); fd.append('file', file.value); fd.append('tag', tag.value); fd.append('description', desc.value);
    await axios.post(`${API}/images/upload`, fd);
    load();
};
const dl = async (id) => {
    try {
        const res = await axios.get(`${API}/images/download/${id}`);
        const url = res.data.presigned_url;
        window.open(url, '_blank');
    } catch (err) {
        console.error(err);
        alert('Download failed');
    }
};
const del = async (id) => { await axios.delete(`${API}/images/${id}`); load(); };
onMounted(load);
</script>