// Copyright 2009-2023 The Mumble Developers. All rights reserved.
// Use of this source code is governed by a BSD-style license
// that can be found in the LICENSE file at the root of the
// Mumble source tree or at <https://www.mumble.info/LICENSE>.

// a few defines required to build out of tree
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#define MUMBLE_ALLOW_DEPRECATED_LEGACY_PLUGIN_API

#include "mumble_legacy_plugin.h"
#include "mumble_positional_audio_main.h"  // Include standard positional audio header.
#include "mumble_positional_audio_utils.h" // Include positional audio header for special functions, like "escape".

static int fetch(float *avatar_pos, float *avatar_front, float *avatar_top, float *camera_pos, float *camera_front,
				 float *camera_top, std::string &context, std::wstring &identity) {
	for (int i = 0; i < 3; i++) {
		avatar_pos[i] = avatar_front[i] = avatar_top[i] = camera_pos[i] = camera_front[i] = camera_top[i] = 0.0f;
	}

	// Memory addresses
	procptr_t state_address				= 0x00BD0792;   // OK
	procptr_t avatar_pos_address		= 0x00ADF4E4;   // OK
	procptr_t avatar_heading_address	= 0x00BEBA70;   // OK
	procptr_t camera_pos_address		= 0x00ADF4E4;	// We use the avatar position instead of camera position, feels more correct in wow
	procptr_t camera_front_address		= 0x00ADF5F0;	// We also use the player orientation instead of the camera front address
	procptr_t camera_top_address		= 0x00ADF554;   // OK
	procptr_t player_address			= 0x00C79D18;   // OK
	procptr_t mapid_address				= 0x00AB63BC;   // OK

	// Boolean value to check if game addresses retrieval is successful
	bool ok;
	// Create containers to stuff our raw data into, so we can convert it to Mumble's coordinate system
	float avatar_pos_corrector[3], camera_pos_corrector[3], avatar_heading, camera_front_corrector[3], camera_top_corrector[3];
	// Char values for extra features
	char state, player[50];
	int mapId;

	// Peekproc and assign game addresses to our containers, so we can retrieve positional data
	ok = peekProc(state_address, &state, 1) &&							// Magical state value: 1 when in-game, 0 when not.
		peekProc(avatar_pos_address, avatar_pos_corrector, 12) &&		// Avatar Position values (Z, -X and Y).
		peekProc(avatar_heading_address, avatar_heading) &&				// Avatar heading.
		peekProc(camera_pos_address, camera_pos_corrector, 12) &&		// Camera Position values (Z, -X and Y).
		peekProc(camera_front_address, camera_front_corrector, 12) &&	// Camera Front Vector values (Z, -X and Y).
		peekProc(camera_top_address, camera_top_corrector, 12) &&		// Camera Top Vector values (Z, -X and Y).
		peekProc(player_address, player) &&								// Player nickname.
		peekProc(mapid_address, mapId);									// Map ID.

	// This prevents the plugin from linking to the game in case something goes wrong during values retrieval from
	// memory addresses.
	if (!ok)
		return false;

	// State
	if (state != 1) {  // If not in-game
		context.clear();  // Clear context
		identity.clear(); // Clear identity
		// Set vectors values to 0.
		for (int i = 0; i < 3; i++)
			avatar_pos[i] = avatar_front[i] = avatar_top[i] = camera_pos[i] = camera_front[i] = camera_top[i] = 0.0f;

		return true; // This tells Mumble to ignore all vectors.
	}

	// Begin context
	std::ostringstream ocontext;

	// Map ID
	if (mapId >= 0) {
		ocontext << " {\"Map ID\": " << mapId << "}"; // Set context with mapid
	}

	context = ocontext.str();
	// End context


	// Begin identity
	std::wostringstream oidentity;
	oidentity << "{";

	// Player
	escape(player, sizeof(player));
	if (strcmp(player, "") != 0) {
		oidentity << std::endl;
		oidentity << "\"Player\": \"" << player << "\""; // Set player nickname in identity.
	} else {
		oidentity << std::endl << "\"Player\": null";
	}

	oidentity << std::endl << "}";
	identity = oidentity.str();
	// End identity

	/*
	Mumble	|	Game
	X		|	Z
	Y		|	-X
	Z		|	Y
	*/
	avatar_pos[0] = -avatar_pos_corrector[1];
	avatar_pos[1] = avatar_pos_corrector[2];
	avatar_pos[2] = avatar_pos_corrector[0];

	camera_pos[0] = -camera_pos_corrector[1];
	camera_pos[1] = camera_pos_corrector[2];
	camera_pos[2] = camera_pos_corrector[0];

	avatar_front[0] = -sin(avatar_heading);
	avatar_front[1] = 0.0f;
	avatar_front[2] = cos(avatar_heading);

	avatar_top[2] = -1; // Dummy top vector, you can't tilt your head sideways in WoW.

	camera_front[0] = -sin(avatar_heading);		//-camera_front_corrector[1];
	camera_front[1] = 0.0f;						//camera_front_corrector[2];
	camera_front[2] = cos(avatar_heading);		//camera_front_corrector[0];

	camera_top[0] = -camera_top_corrector[1];
	camera_top[1] = camera_top_corrector[2];
	camera_top[2] = camera_top_corrector[0];

	return true;
}

static int trylock(const std::multimap< std::wstring, unsigned long long int > &pids) {
	if (!initialize(pids, L"Wow.exe")) { // Retrieve game executable's memory address
		return false;
	}

	// Check if we can get meaningful data from it
	float apos[3], afront[3], atop[3], cpos[3], cfront[3], ctop[3];
	std::wstring sidentity;
	std::string scontext;

	if (fetch(apos, afront, atop, cpos, cfront, ctop, scontext, sidentity)) {
		return true;
	} else {
		generic_unlock();
		return false;
	}
}

static const std::wstring longdesc() {
	return std::wstring(
		L"Supports World of Warcraft (x86) with identity support.");				// Plugin long description
}

static std::wstring description(L"World of Warcraft (x86) version 3.3.5a.12340");   // Plugin short description
static std::wstring shortname(L"World of Warcraft 3.3.5a");							// Plugin short name

static int trylock1() {
	return trylock(std::multimap<std::wstring, unsigned long long int>());
}

static MumblePlugin wow3plug = {
	MUMBLE_PLUGIN_MAGIC,
	description,
	shortname,
	NULL,
	NULL,
	trylock1,
	generic_unlock,
	longdesc,
	fetch
};

static MumblePlugin2 wow3plug2 = {
	MUMBLE_PLUGIN_MAGIC_2,
	MUMBLE_PLUGIN_VERSION,
	trylock
};

extern "C" MUMBLE_PLUGIN_EXPORT MumblePlugin *getMumblePlugin() {
	return &wow3plug;
}

extern "C" MUMBLE_PLUGIN_EXPORT MumblePlugin2 *getMumblePlugin2() {
	return &wow3plug2;
}