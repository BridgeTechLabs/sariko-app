import { Quasar, Loading, Notify, Dialog } from 'quasar'
import iconSet from 'quasar/icon-set/svg-material-icons'

export default function useQuasarPlugin(app) {
    console.log("Loaded Quasar plugin")
    app.use(Quasar, {
        plugins: { Loading, Notify, Dialog }, // Quasar plugins
        iconSet: iconSet,
        config: {
            brand: {
                bgInputField: '#040A14',
            }
        }
    })
}