
export def container-provider []: nothing -> record<command: string, path: string, type: string> {
    let commands = [...(which podman), ...(which docker)];

    if ($commands | length) == 0 {
        error make --unspanned { msg: "Cannot find `podman` or `docker`" }
    }

    $commands.0
}

def startup_containers []: nothing -> nothing {
    let provider = container-provider;

    try {
        ^$provider.command compose --profile tests config | ignore;
    } catch {
        |err| $err.msg;
    }

    try {
        print "\n::: Starting up containers for tests...\n";
        ^$provider.command compose --profile tests up -d --remove-orphans;
    } catch {
          |err| $err.msg;
    }
}

def shutdown_containers []: nothing -> nothing {
    let provider = container-provider;

    try {
        print "\n::: Shutting down containers...\n";
        ^$provider.command compose --profile tests down;
    } catch {
        |err| $err.msg;
    }
}

export def tests [
    path: path = ".",
    # --coverage = true,
    --verbose = true
]: nothing -> nothing {
    mut args = [];

    # if ($coverage) {
    #     $args = [...$args, --cov=src];
    # }

    if ($verbose) {
        $args = [...$args, -vvv];
    }

    $args = [...$args, $path];
    
    startup_containers;
    
    try {
        print "\n::: Running tests...\n"
        uv run pytest ...$args;
    } catch {
        |err| $err.msg;
    }
    
    shutdown_containers; 

    print "\n::: Done."
}
