import { createApp } from 'vue';
import App from './App.vue';
import router from './router'; // Import the router we just fixed
import PrimeVue from 'primevue/config';

// PrimeVue Component Imports
import Button from 'primevue/button';
import InputText from 'primevue/inputtext';
import Card from 'primevue/card';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Tag from 'primevue/tag';

// Styles
import "primevue/resources/themes/lara-light-blue/theme.css";
import "primevue/resources/primevue.min.css";
import "primeicons/primeicons.css";
import "primeflex/primeflex.css";

const app = createApp(App);

// Register components globally for easier use
app.component('Button', Button);
app.component('InputText', InputText);
app.component('Card', Card);
app.component('DataTable', DataTable);
app.component('Column', Column);
app.component('Tag', Tag);

app.use(router);
app.use(PrimeVue);

app.mount('#app');