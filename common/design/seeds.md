# Seeds: design policy

This is a permanent policy. It says what the seeds must guarantee and why; the chain of seeds itself is documented
in the docstring of `galaxies/seeds.py`, and the code that uses it in the modules that own each object.

## The guarantee

A galaxy seed given by the player always produces the same universe: the same stars, systems, planets, outposts,
people, rocks and missions. That holds for:

- a new game with that seed, started today or later;
- a load of a save made with that seed;
- any order in which the player visits the universe.

Generated content is never saved. A save holds only what the player changed (the alterations), and everything else is
generated again from the seed. If generation changed for the same seed, a save would point at objects that no longer
exist.

## The rules

1. **Each object has its own seed, derived from its parent's seed.** The derivation names the child's kind and the
   keys that place it in its parent. Example: an orbit is derived from its system and its number; a planet from its
   orbit and its index in that orbit. The seed never depends on what else has been generated.
2. **Keys identify, they do not count.** A key is a fixed identity of the child in its parent: an index, a number, a
   position in a fixed grid. It is never "the next one generated". Example: a rock's key is its position in its Km2,
   so the rock at a given position is the same rock whether the Km2 was generated first or last.
3. **No global state in generation.** Generation does not use the global random module, a counter, or the order of
   visits. Each object draws from its own generator, seeded with its seed.
4. **Draws are in a fixed order.** Each object draws its values in a set order. During development, a new draw goes
   last whenever that costs nothing in realism or in the clean structure of the code; when it does cost something, the
   order is changed instead. After deployment the order is frozen (see "Two phases" below).
5. **Seeds are whole numbers, and distinct parents give distinct children.** A seed is not built by arithmetic on the
   parent's seed (sums, products, modulo), because those collide: two different parents can give the same child.
   Example: adding the index to the parent's seed makes child 0 of one parent equal to child 1 of its neighbour. Seeds
   are built by hashing the parent, the kind and the keys together.
6. **Floats are never seeds for the generator.** Hashing a float depends on the runtime, and a small range of seeds
   gives small universes. The galaxy seed is the one value the player gives, and it is the root of the chain.
7. **Regions are keyed by their absolute index.** A region of space (a sector, a district) is named by where it is in
   the galaxy, not by its place among the regions generated so far. So its key does not change with the way space is
   cut or with what was visited first.

## What this means in practice

- Visiting system A then system B gives the same objects as visiting B then A.
- A new game and a load of the same seed give the same objects, so a person saved by seed can be found again.
- A new kind of object gets its own kind name in its derivation, so it cannot collide with an existing kind.
## Two phases

- **Development (before deployment).** The code may change what a seed generates: a derivation, a key, the order of
  draws, even how the code is grouped. Results can change for every seed, and existing saves may stop matching. This
  is accepted, and the change should be made cleanly rather than preserved with workarounds such as sub-seeds.
- **Deployed.** A new game with the same seed, and a load of a save, must generate the same objects for the same
  situations in the universe. A change that alters generated content for existing seeds is then a decision for the
  user, and it breaks existing saves.

## Exceptions

The guarantee is generic, with two kinds of exception:

- **Player interaction.** What the player did can change the course of the universe, so the objects it affects may
  differ from a fresh generation. The player's changes are saved as alterations, which is how they persist.
- **Trivial events.** Where an event is too small to matter to the game, it may vary.

Each exception should be named where it is made, not assumed.

## Tests that guard it

- Generate the same objects in two processes in opposite orders, and compare a digest of what was produced.
- Check that the seeds of the objects of one galaxy are all distinct.
- Save and load a game, and check that the people and the objects saved by seed are found again.
