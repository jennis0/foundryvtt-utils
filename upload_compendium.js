async function import_json(filename, moduleName, packName) {
  console.log(game.packs)
  const pack = game.packs.find(p => p.collection === `${moduleName}.${packName}`);
  const response = await fetch(filename);
	const content = await response.json();

  const index = await pack.getIndex();
  for (let ent of index) {
    await pack.deleteEntity(ent._id)
  }
  console.log(index)
  
	//Save content into the Compendium pack
	for ( let t of content ) {
	  await pack.createEntity(t);
	  console.log(`Imported RollTable ${t.name} into Compendium pack ${pack.collection}`);
  }
}

import_json("worlds/import/data.js", "world", "new-compendium");
