// QĐ3-11 "Edit for this dish only": the dish gets a copy of a shared group, in the old group's place; the other
// dishes keep the old group. Three calls: take the old group off, create the copy (it goes last), put it back in
// the old place. If the create fails (e.g. the store's group cap) the old group goes back in its place. If only the
// last step fails, the copy stays last and no error goes up: the form closes, a retry would stack a second copy.
// `api` is apiSellerMenu, passed in so tests/frontend can fake it.
export async function copyGroupForDish(api, dishId, groupIds, oldId, body) {
    await api.detachOptionGroup(dishId, oldId)
    let group
    try {
        group = (await api.createOptionGroup(dishId, body)).group
    } catch (e) {
        await api.attachOptionGroup(dishId, oldId)
        await api.orderOptionGroups(dishId, groupIds)
        throw e
    }
    await api.orderOptionGroups(dishId, groupIds.map(id => (id === oldId ? group.id : id)))
        .catch(e => console.error('copyGroupForDish - order -', e))
    return group
}
